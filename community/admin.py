from django.contrib import admin
from .models import Event, Notice, Advertisement

from django.contrib import admin
from dashboard.models import Village

admin.site.register(Event)
admin.site.register(Notice)
admin.site.register(Advertisement)


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "name_gu", "is_active")
    list_display_links = ("name",)
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    search_fields = ("name", "name_gu")
    ordering = ("number", "name")




