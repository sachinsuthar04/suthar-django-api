from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Notification
from .serializers import NotificationSerializer


# -----------------------------
# 1. Get All Notifications (for logged in user)
# -----------------------------
from django.db.models import Q

class NotificationListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notif_type = request.query_params.get("type")

        qs = Notification.objects.filter(
            Q(user=request.user) | Q(user__isnull=True)
        )

        if notif_type:
            qs = qs.filter(type=notif_type)

        serializer = NotificationSerializer(qs, many=True)

        return Response({
            "success": True,
            "notifications": serializer.data
        })






# -----------------------------
# 2. Get Single Notification (by id)
# -----------------------------
class NotificationDetailAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        notification = Notification.objects.filter(
            id=pk,
            user=request.user
        ).first()

        if not notification:
            return Response({
                "success": True,
                "notifications": []
            })

        serializer = NotificationSerializer(notification)

        return Response({
            "success": True,
            "notifications": [serializer.data]  # 👈 FORCE LIST
        })



# -----------------------------
# 3. Mark Notification as Read/Unread
# -----------------------------
class MarkNotificationReadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(
            Notification,
            id=pk,
            user=request.user
        )

        is_read = request.data.get("is_read")

        if is_read is None:
            return Response({
                "success": False,
                "error": "is_read field is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        notification.is_read = bool(is_read)
        notification.save()

        return Response({
            "success": True,
            "message": "Notification updated successfully"
        }, status=status.HTTP_200_OK)
