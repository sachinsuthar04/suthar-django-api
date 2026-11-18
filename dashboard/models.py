from django.db import models


class Village(models.Model):
    """A village of the samaj (Kantha Sattavis: 35 villages).

    `name` (English) is what the app stores in a member's native place;
    `name_gu` is shown to Gujarati users. Villages are never hard-deleted
    from the app: admins switch `is_active` off so old profiles keep a
    valid native place.
    """
    name = models.CharField(max_length=255, unique=True, default="")
    name_gu = models.CharField("Gujarati name", max_length=255, blank=True, default="")
    number = models.PositiveIntegerField("List no.", default=0, help_text="Order in the village list")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ("number", "name")

    def __str__(self):
        return f"{self.name} ({self.name_gu})" if self.name_gu else self.name
