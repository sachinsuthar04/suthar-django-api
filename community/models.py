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

    def __str__(self):
        return self.title


class Notice(BaseCommunityModel):
    notice_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title


class Advertisement(BaseCommunityModel):
    ad_date = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.title
