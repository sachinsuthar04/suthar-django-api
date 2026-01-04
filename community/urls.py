from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, NoticeViewSet, AdvertisementViewSet

router = DefaultRouter()
router.register('events', EventViewSet, basename='events')
router.register('notices', NoticeViewSet, basename='notices')
router.register('advertisements', AdvertisementViewSet, basename='advertisements')

urlpatterns = [
    path('', include(router.urls)),
]
