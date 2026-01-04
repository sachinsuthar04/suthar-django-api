from rest_framework.permissions import IsAuthenticated
from .models import Event, Notice, Advertisement
from .serializers import EventSerializer, NoticeSerializer, AdvertisementSerializer
from .base_viewset import BaseModelViewSet


class EventViewSet(BaseModelViewSet):
    queryset = Event.objects.all().order_by('-created_at')
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]


class NoticeViewSet(BaseModelViewSet):
    queryset = Notice.objects.all().order_by('-created_at')
    serializer_class = NoticeSerializer
    permission_classes = [IsAuthenticated]


class AdvertisementViewSet(BaseModelViewSet):
    queryset = Advertisement.objects.all().order_by('-created_at')
    serializer_class = AdvertisementSerializer
    permission_classes = [IsAuthenticated]
