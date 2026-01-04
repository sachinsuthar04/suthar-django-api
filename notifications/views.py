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
class NotificationListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            "success": True,
            "notifications": serializer.data
        }, status=status.HTTP_200_OK)


# -----------------------------
# 2. Get Single Notification (by id)
# -----------------------------
class NotificationDetailAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        notification = get_object_or_404(
            Notification,
            id=pk,
            user=request.user  # ✅ user can access only own notification
        )
        serializer = NotificationSerializer(notification)

        return Response({
            "success": True,
            "notification": serializer.data
        }, status=status.HTTP_200_OK)


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
