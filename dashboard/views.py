from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from community.models import Advertisement, Event, Notice
from users.models import User
from notifications.models import Notification


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Village



dashboard_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "notificationCount": openapi.Schema(type=openapi.TYPE_INTEGER),
        "stats": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "totalMembers": openapi.Schema(type=openapi.TYPE_INTEGER),
                "upcomingEvents": openapi.Schema(type=openapi.TYPE_INTEGER),
                "latestNotices": openapi.Schema(type=openapi.TYPE_INTEGER),
                "totalAds": openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
    },
)
home_content_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "notificationSwitchStatus": openapi.Schema(type=openapi.TYPE_BOOLEAN),
        "blocks": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "upcomingEvents": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "title": openapi.Schema(type=openapi.TYPE_STRING),
                        "image": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        "date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                    },
                )),
                "advertisements": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "title": openapi.Schema(type=openapi.TYPE_STRING),
                        "image": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        "date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                    },
                )),
                "notices": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "title": openapi.Schema(type=openapi.TYPE_STRING),
                        "image": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        "date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                    },
                )),
            }
        ),
    },
)

class DashboardAPI(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Dashboard data",
        responses={200: dashboard_response_schema},
        tags=["Dashboard"]
    )
    def get(self, request):
        user = request.user
        today = timezone.now().date()

        total_members = User.objects.count()
        upcoming_events = Event.objects.filter(event_date__gte=today).count()
        latest_notices = Notice.objects.count()
        total_ads = Advertisement.objects.count()
        notification_count = Notification.objects.filter(
            user=user, is_read=False
        ).count()

        return Response({
            "notificationCount": notification_count,
            "stats": {
                "totalMembers": total_members,
                "upcomingEvents": upcoming_events,
                "latestNotices": latest_notices,
                "totalAds": total_ads,
            }
        })

class HomeContentAPI(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Home content data",
        responses={200: home_content_response_schema},
        tags=["Dashboard"]
    )
    def get(self, request):
        user = request.user
        today = timezone.now().date()

        notification_switch_status = getattr(user, "notificationEnable", False)

        # 🔹 Upcoming Events
        events_qs = Event.objects.filter(
            event_date__gte=today
        ).order_by("event_date")[:5]

        upcoming_events = [
            {
                "id": event.id,
                "title": event.title,
                "image": event.image.url if event.image else None,
                "date": event.event_date,
            }
            for event in events_qs
        ]

        # 🔹 Advertisements
        ads_qs = Advertisement.objects.order_by("-created_at")[:5]
        advertisements = [
            {
                "id": ad.id,
                "title": ad.title,
                "image": ad.image.url if ad.image else None,
                "date": ad.created_at,
            }
            for ad in ads_qs
        ]

        # 🔹 Notices
        notices_qs = Notice.objects.order_by("-created_at")[:5]
        notices = [
            {
                "id": notice.id,
                "title": notice.title,
                "image": notice.image.url if notice.image else None,
                "date": notice.notice_date or notice.created_at,
            }
            for notice in notices_qs
        ]

        return Response({
            "notificationSwitchStatus": notification_switch_status,
            "blocks": {
                "upcomingEvents": upcoming_events,
                "advertisements": advertisements,
                "notices": notices,
            }
        })


# Swagger schema for City List Response
village_list_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "village": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "name": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
        )
    }
)
class VillageListAPI(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all village list",
        responses={200: village_list_schema},
    )
    def get(self, request):
        villages = list(
            Village.objects.all()
            .values("id", "name")
            .order_by("name")
        )

        return Response({"village": villages})
