from django.urls import path
from .views import (
    MemberListView,
    ApproveMemberView,
    FamilyHeadAddMember,
    FamilyHeadUpdateMember,
    MyFamilyMembers,
    MemberDetailView
)

urlpatterns = [
    path('all/', MemberListView.as_view()),             # Admin
    path('accept-reject/<int:pk>/', ApproveMemberView.as_view()),  # Admin
    path('add/', FamilyHeadAddMember.as_view()),       # Family head
    path( 'update/<int:member_id>/', FamilyHeadUpdateMember.as_view(), name='family-head-update-member'),
    path('my-family/', MyFamilyMembers.as_view()),      # Logged user
    path('<int:pk>/', MemberDetailView.as_view()),      # Detail + Update
]
