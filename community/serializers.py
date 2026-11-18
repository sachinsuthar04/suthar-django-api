from rest_framework import serializers
from .models import Event, Notice, Advertisement, going_families


# -----------------------------
# Event Serializer
# -----------------------------
class EventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    going_count = serializers.SerializerMethodField()
    i_am_going = serializers.SerializerMethodField()

    def get_going_count(self, obj):
        return going_families(obj)

    def get_i_am_going(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.rsvps.filter(member__user=request.user).exists()

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
