from django.db import models
from users.models import User


class NotificationType(models.TextChoices):
    EVENT = "event", "Event Reminder"
    APPROVAL = "approval", "Approval / Reject"
    COMMUNITY = "community", "Community Update"
    GENERAL = "general", "General Notification"


class Notification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title = models.CharField(max_length=200)
    message = models.TextField()

    type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )

    is_read = models.BooleanField(default=False)

    reference_id = models.CharField(max_length=50, null=True, blank=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.id} -> {self.title}"
