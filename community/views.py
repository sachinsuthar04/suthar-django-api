from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from members.permissions import IsActiveMember, get_active_member
from notifications.models import Notification
from .models import Event, EventRSVP, Notice, Advertisement, going_families
from .serializers import EventSerializer, NoticeSerializer, AdvertisementSerializer
from .base_viewset import BaseModelViewSet


class EventViewSet(BaseModelViewSet):
    queryset = Event.objects.all().order_by('-created_at')
    serializer_class = EventSerializer

    @action(detail=True, methods=["post"], url_path="rsvp",
            permission_classes=[IsAuthenticated, IsActiveMember])
    def rsvp(self, request, pk=None):
        """POST {"going": true|false}  (omit to toggle). Only approved members."""
        event = self.get_object()
        member = get_active_member(request.user)
        if member is None:
            return Response({"success": False, "message": "Only members can RSVP."}, status=403)

        existing = EventRSVP.objects.filter(event=event, member=member)
        wanted = request.data.get("going")
        going = (not existing.exists()) if wanted is None else str(wanted).lower() in ("1", "true", "yes")

        if going:
            EventRSVP.objects.get_or_create(event=event, member=member)
        else:
            existing.delete()

        return Response({"success": True, "going": going, "goingCount": going_families(event)})

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
