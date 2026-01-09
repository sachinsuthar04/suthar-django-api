
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from community.views import EventViewSet, NoticeViewSet, AdvertisementViewSet

router = DefaultRouter()

router.register('events', EventViewSet, basename='events')
router.register('notices', NoticeViewSet, basename='notices')
router.register('ads', AdvertisementViewSet, basename='ads')

urlpatterns = [
    path('', include(router.urls)),
]
