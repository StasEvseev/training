from celery import shared_task
from celery.utils.time import get_exponential_backoff_interval
from django.db.models import Avg, Max
import logging

from celery import Celery

from locks import acquire_lock_process_all_workouts
from models import WorkoutResult, Sample
from services import get_all_unprocessed_workouts

logger = logging.getLogger(__name__)

celery_app = Celery(
    "training_app",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        600.0, process_all_workouts.s(), name="Process workouts every 10 min"
    )


@shared_task(bind=True, max_retries=3, acks_late=True, retry_for=(Exception,))
def process_all_workouts(self):
    # Только один инстанс задачи может выполняться в один момент времени
    with acquire_lock_process_all_workouts() as have_lock:
        if not have_lock:
            logger.info("Task is already running, skipping execution.")
            return  # Прерываем выполнение, если лок уже держится

        # Инициализируем подсчет всех тренировок без результата
        # Здесь же мы можем адаптировать логику для обработки воркаутов по приоритету(разные типы тренировок, пользователи и т.д.)
        # или обработки только определенного количества тренировок за раз
        for workout in get_all_unprocessed_workouts():
            process_workout.apply_async(args=[workout])


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
)
def process_workout(self, workout_id):
    workout_result = None
    try:
        # Получаем или создаем объект результата
        workout_result, created = WorkoutResult.objects.get_or_create(
            workout_id=workout_id,
            defaults={"status": WorkoutResult.WorkoutStatus.PENDING},
        )

        if (
            not created
            and workout_result.status == WorkoutResult.WorkoutStatus.COMPLETED
        ):
            return

        workout_result.status = WorkoutResult.WorkoutStatus.PROCESSING
        workout_result.save()

        # Получаем агрегированные данные
        samples = Sample.objects.filter(workout_id=workout_id)

        # Тут нужно смотреть, можно ли нагружать базу для подсчета агрегированных данных
        # как альтернативу можно делать подсчет в самом воркере чтобы не нагружать базу
        aggregates = samples.aggregate(
            avg_heart_rate=Avg("heart_rate"), max_heart_rate=Max("heart_rate")
        )

        # Обновляем результат
        workout_result.avg_heart_rate = aggregates["avg_heart_rate"]
        workout_result.max_heart_rate = aggregates["max_heart_rate"]
        workout_result.status = WorkoutResult.WorkoutStatus.COMPLETED
        workout_result.save()
    except Exception as exc:
        logger.error(
            "Error processing workout {workout_id}",
            workout_id=workout_id,
            exc_info=True,
        )
        if workout_result:
            workout_result.status = WorkoutResult.WorkoutStatus.FAILED
            workout_result.error_message = str(exc)
            workout_result.save()
        countdown = get_exponential_backoff_interval(
            factor=10,
            retries=self.request.retries,
            maximum=600,
            full_jitter=True,
        )
        raise self.retry(exc=exc, countdown=countdown)
