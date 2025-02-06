from enum import Enum

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Workout(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "date"]),
        ]


class Sample(models.Model):
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE)
    heart_rate = models.IntegerField()
    timestamp = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["workout", "timestamp"]),
        ]


class WorkoutResult(models.Model):
    class WorkoutStatus(Enum):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    workout = models.OneToOneField(Workout, on_delete=models.CASCADE)
    avg_heart_rate = models.FloatField()
    max_heart_rate = models.IntegerField()
    processed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.name.capitalize()) for tag in WorkoutStatus],
        default=WorkoutStatus.PENDING.value,
    )
    error_message = models.TextField(null=True, blank=True)
