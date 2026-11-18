from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import timedelta
from django.utils import timezone

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from community.models import Advertisement, Event, EventRSVP, Notice, going_families
from users.models import User
from notifications.models import Notification


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Village
from members.models import Member, MemberStatus
from members.permissions import IsActiveMember, IsAppAdmin, get_member
from rest_framework import serializers



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
    permission_classes = [IsAuthenticated, IsActiveMember]

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
    permission_classes = [IsAuthenticated, IsActiveMember]

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
                    "name_gu": openapi.Schema(type=openapi.TYPE_STRING),
                    "number": openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            ),
        )
    }
)
class VillageListAPI(APIView):
    """Active villages for the registration / profile dropdown."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all village list",
        responses={200: village_list_schema},
    )
    def get(self, request):
        villages = list(
            Village.objects.filter(is_active=True)
            .order_by("number", "name")
            .values("id", "name", "name_gu", "number")
        )
        return Response({"village": villages})


class VillageSerializer(serializers.ModelSerializer):
    memberCount = serializers.IntegerField(source="member_count", read_only=True, default=0)

    class Meta:
        model = Village
        fields = ("id", "number", "name", "name_gu", "is_active", "memberCount")

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Village name is required.")
        qs = Village.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A village with this name already exists.")
        return value

    def validate_name_gu(self, value):
        return (value or "").strip()


def _villages_with_counts():
    """Every village + how many members have it as native place (English or Gujarati name)."""
    villages = list(Village.objects.order_by("number", "name"))
    counts = {}
    for place in Member.objects.exclude(native_place__isnull=True).exclude(native_place="").values_list("native_place", flat=True):
        key = place.strip().lower()
        counts[key] = counts.get(key, 0) + 1
    for v in villages:
        v.member_count = counts.get(v.name.lower(), 0) + (counts.get(v.name_gu.lower(), 0) if v.name_gu else 0)
    return villages


class AdminVillageListCreateAPI(APIView):
    """Admin: all villages (active and switched off) with member counts; add a village."""
    permission_classes = [IsAuthenticated, IsAppAdmin]

    @swagger_auto_schema(operation_summary="Admin: list villages", tags=["Villages"])
    def get(self, request):
        villages = _villages_with_counts()
        return Response({
            "village": VillageSerializer(villages, many=True).data,
            "total": len(villages),
            "active": sum(1 for v in villages if v.is_active),
        })

    @swagger_auto_schema(operation_summary="Admin: add village", request_body=VillageSerializer, tags=["Villages"])
    def post(self, request):
        s = VillageSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not s.validated_data.get("number"):
            last = Village.objects.filter(number__lt=1000).order_by("-number").first()
            s.validated_data["number"] = (last.number if last else 0) + 1
        v = s.save()
        v.member_count = 0
        return Response({"success": True, "message": "Village added", "village": VillageSerializer(v).data}, status=201)


class AdminVillageDetailAPI(APIView):
    """Admin: edit a village, or delete it (a village members still use is only switched off)."""
    permission_classes = [IsAuthenticated, IsAppAdmin]

    def _get(self, pk):
        return Village.objects.filter(pk=pk).first()

    @swagger_auto_schema(operation_summary="Admin: edit village", request_body=VillageSerializer, tags=["Villages"])
    def patch(self, request, pk):
        v = self._get(pk)
        if not v:
            return Response({"success": False, "message": "Village not found"}, status=404)
        old_name = v.name
        s = VillageSerializer(v, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        v = s.save()
        if old_name != v.name:
            # keep members' native place pointing at the renamed village
            Member.objects.filter(native_place__iexact=old_name).update(native_place=v.name)
        v.member_count = next((x.member_count for x in _villages_with_counts() if x.pk == v.pk), 0)
        return Response({"success": True, "message": "Village updated", "village": VillageSerializer(v).data})

    put = patch

    @swagger_auto_schema(operation_summary="Admin: delete village", tags=["Villages"])
    def delete(self, request, pk):
        v = self._get(pk)
        if not v:
            return Response({"success": False, "message": "Village not found"}, status=404)
        used = next((x.member_count for x in _villages_with_counts() if x.pk == v.pk), 0)
        if used:
            v.is_active = False
            v.save(update_fields=["is_active", "updated_at"])
            return Response({
                "success": True, "deleted": False,
                "message": f"{used} member(s) belong to this village, so it was switched off instead of deleted.",
            })
        v.delete()
        return Response({"success": True, "deleted": True, "message": "Village deleted"})


class HomeSummaryAPI(APIView):
    """
    One call for the Home screen: who am I (name, role, village), the next
    event (with my RSVP), counters, latest notices (with category) and ads
    (with place and price).
    """
    permission_classes = [IsAuthenticated, IsActiveMember]

    @swagger_auto_schema(operation_summary="Home screen summary", tags=["Dashboard"])
    def get(self, request):
        user = request.user
        me = get_member(user)
        today = timezone.now().date()
        since = timezone.now() - timedelta(days=30)

        def event_row(ev):
            return {
                "id": ev.id,
                "title": ev.title,
                "description": ev.description,
                "image": request.build_absolute_uri(ev.image.url) if ev.image else None,
                "date": ev.event_date,
                "time": ev.event_time.strftime("%H:%M") if ev.event_time else None,
                "location": ev.location,
                "goingCount": going_families(ev),
                "iAmGoing": bool(me and ev.rsvps.filter(member=me).exists()),
            }

        events = list(Event.objects.filter(event_date__gte=today).order_by("event_date", "event_time")[:5])
        notices = Notice.objects.order_by("-created_at")[:5]
        ads = Advertisement.objects.order_by("-created_at")[:6]

        village = ""
        if me:
            village = me.native_place or me.city or ""

        return Response({
            "success": True,
            "me": {
                "name": me.name if me else (getattr(user, "email", "") or ""),
                "role": me.role if me else "admin",
                "village": village,
                "familyCode": me.family_display_id if me else None,
            },
            "unreadNotifications": Notification.objects.filter(user=user, is_read=False).count(),
            "stats": {
                "members": Member.objects.filter(status=MemberStatus.ACTIVE).count(),
                "upcomingEvents": Event.objects.filter(event_date__gte=today).count(),
                "newNotices": Notice.objects.filter(created_at__gte=since).count(),
            },
            "nextEvent": event_row(events[0]) if events else None,
            "events": [event_row(e) for e in events],
            "notices": [
                {
                    "id": n.id,
                    "title": n.title,
                    "body": n.description,
                    "category": n.category,
                    "date": n.notice_date or n.created_at.date(),
                    "location": n.location,
                    "image": request.build_absolute_uri(n.image.url) if n.image else None,
                }
                for n in notices
            ],
            "ads": [
                {
                    "id": a.id,
                    "title": a.title,
                    "location": a.location,
                    "price": str(a.price) if a.price is not None else None,
                    "image": request.build_absolute_uri(a.image.url) if a.image else None,
                }
                for a in ads
            ],
        })
