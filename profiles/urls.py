from django.urls import path
from .views import SaveUserProfileAPI, ProfileDetailView, UploadProfileImageView

urlpatterns = [
    path("profile/<int:user_id>/", ProfileDetailView.as_view(), name="get-profile"),
    path("profile/save/", SaveUserProfileAPI.as_view(), name="save-user-profile"),
    path("profile/upload-image/", UploadProfileImageView.as_view()),
]
