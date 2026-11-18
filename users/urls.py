from django.urls import path
from .views import AdminLoginView, SaveFcmTokenView

urlpatterns = [
    path('admin-login/', AdminLoginView.as_view(), name='admin-login'),
    path('save-fcm-token/', SaveFcmTokenView.as_view(), name='save-fcm-token'),
]
