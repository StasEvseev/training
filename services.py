from django.db.models import QuerySet

from models import Workout


def get_all_unprocessed_workouts() -> QuerySet[int]:
    return Workout.objects.filter(workoutresult__isnull=True).values_list(
        "id", flat=True
    )
