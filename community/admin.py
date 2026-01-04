from django.contrib import admin
from .models import Event, Notice, Advertisement

from django.contrib import admin
from dashboard.models import Village

admin.site.register(Event)
admin.site.register(Notice)
admin.site.register(Advertisement)
admin.site.register(Village)


class VillageAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)




