from rest_framework import serializers
from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "type",
            "is_read",
            "reference_id",
            "reference_type",
            "created_at",
        ]
