
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import MemberViewSet
from families.views import FamilyViewSet
from community.views import EventViewSet, NoticeViewSet, AdvertisementViewSet

router = DefaultRouter()
router.register('members', MemberViewSet, basename='members')
router.register('families', FamilyViewSet, basename='families')
router.register('events', EventViewSet, basename='events')
router.register('notices', NoticeViewSet, basename='notices')
router.register('ads', AdvertisementViewSet, basename='ads')

urlpatterns = [
    path('', include(router.urls)),
]
