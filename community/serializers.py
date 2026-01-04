from rest_framework import serializers
from .models import Event, Notice, Advertisement


# -----------------------------
# Event Serializer
# -----------------------------
class EventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Event
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")


# -----------------------------
# Notice Serializer
# -----------------------------
class NoticeSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Notice
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")


# -----------------------------
# Advertisement Serializer
# -----------------------------
class AdvertisementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Advertisement
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")
