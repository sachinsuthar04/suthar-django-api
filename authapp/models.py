from django.db import models
from django.utils import timezone
from datetime import timedelta
import random

# authapp/models.py

class OTP(models.Model):
    country_code = models.CharField(max_length=5, default="+91")
    phone = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = str(random.randint(100000, 999999))
        super().save(*args, **kwargs)

