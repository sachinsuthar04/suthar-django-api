from django.db import models

class Village(models.Model):
    name = models.CharField(max_length=255, unique=True, default="Unknown Village")
    def __str__(self):
        return self.name
