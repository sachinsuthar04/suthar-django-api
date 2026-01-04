from django.urls import path
from .views import (
    NotificationListAPI,
    NotificationDetailAPI,
    MarkNotificationReadAPI
)

urlpatterns = [
    # ✅ Get all notifications for logged-in user
    path('my/', NotificationListAPI.as_view()),

    # ✅ Get single notification by ID (only own data)
    path('<int:pk>/', NotificationDetailAPI.as_view()),

    # ✅ Mark notification as read/unread
    path('mark-read/<int:pk>/', MarkNotificationReadAPI.as_view()),
]
