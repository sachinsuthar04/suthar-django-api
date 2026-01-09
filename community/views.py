from rest_framework.permissions import IsAuthenticated

from notifications.models import Notification
from .models import Event, Notice, Advertisement
from .serializers import EventSerializer, NoticeSerializer, AdvertisementSerializer
from .base_viewset import BaseModelViewSet


class EventViewSet(BaseModelViewSet):
    queryset = Event.objects.all().order_by('-created_at')
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        # 1️⃣ Save event
        event = serializer.save(created_by=self.request.user)

        # 2️⃣ Create notification (PUBLIC)
        Notification.objects.create(
            title=event.title,
            message=f"New event created",
            type="event",
            reference_id=event.id,
            reference_type="event",
            action_date=event.event_date,  # optional but useful
        )


class NoticeViewSet(BaseModelViewSet):
    queryset = Notice.objects.all().order_by('-created_at')
    serializer_class = NoticeSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        notice = serializer.save(created_by=self.request.user)

        Notification.objects.create(
            title=notice.title,
            message="New notice announced",
            type="notice",
            reference_id=notice.id,
            reference_type="notice",
            action_date=notice.notice_date,
        )


class AdvertisementViewSet(BaseModelViewSet):
    queryset = Advertisement.objects.all().order_by('-created_at')
    serializer_class = AdvertisementSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        ad = serializer.save(created_by=self.request.user)

        Notification.objects.create(
            title=ad.title,
            message="New advertisement announced",
            type="advertise",
            reference_id=ad.id,
            reference_type="advertise",
            action_date=ad.ad_date,
        )
