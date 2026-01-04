from django.db import models

class Community(models.IntegerChoices):
    SUTHAR = 1, "Suthar"
    PATEL = 2, "Patel"
    MEHTA = 3, "Mehta"
