from django.db import models
from users.models import User

class Notification(models.Model):
    TYPE_CHOICES = (
        ("event", "Event"),
        ("notice", "Notice"),
        ("advertise", "Advertise"),
        ("approve", "Approve"),
        ("reject", "Reject"),
     
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)

    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # ⭐ OPTIONAL – actual event/notice date
    action_date = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        PUBLIC_TYPES = ["event", "notice", "advertise"]

        if self.type in PUBLIC_TYPES:
            self.user = None  # force global
        else:
            if self.user is None:
                raise ValueError("User is required for approve/reject notifications")

        super().save(*args, **kwargs)


