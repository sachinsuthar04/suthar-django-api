from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "title",
        "type",
        "is_read",
        "action_date",   # 👈 optional event/notice date
        "created_at",
    )

    list_filter = (
        "type",
        "is_read",
        "created_at",
        "action_date",
    )

    search_fields = (
        "title",
        "message",
        "user__phone",
        "user__username",
    )

    ordering = ("-created_at",)

    list_editable = ("is_read",)   # ✅ quick toggle

    readonly_fields = ("created_at",)

    date_hierarchy = "created_at"  # ✅ top date navigation

