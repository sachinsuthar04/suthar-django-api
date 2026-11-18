from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class BaseCommunityModel(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='community/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.CharField(max_length=255, null=True, blank=True)


    class Meta:
        abstract = True


class Event(BaseCommunityModel):
    event_date = models.DateField(null=True, blank=True)
    event_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Notice(BaseCommunityModel):
    CATEGORY_CHOICES = (("important", "Important"), ("general", "General"))

    notice_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")

    def __str__(self):
        return self.title


class Advertisement(BaseCommunityModel):
    ad_date = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.title


class EventRSVP(models.Model):
    """A member says "I will attend". One row per member and event."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="event_rsvps")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "member"], name="unique_rsvp_per_member_event")
        ]

    def __str__(self):
        return f"{self.member_id} -> {self.event_id}"


def going_families(event) -> int:
    """People are counted per household ("86 families going"); a member
    without a household counts as one."""
    keys = set()
    for family_id, member_id in event.rsvps.values_list("member__family_id", "member_id"):
        keys.add(("f", family_id) if family_id else ("m", member_id))
    return len(keys)
