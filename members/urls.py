from django.urls import path
from .views import (
    MemberListView,
    ApproveMemberView,
    FamilyHeadAddMember,
    FamilyHeadUpdateMember,
    FamilyHeadDeleteMember,
    MyFamilyMembers,
    MemberDetailView,
    FamilyTreeView,
    MemberSearchView,
    RelationshipRequestView,
    RelationshipRequestRespondView,
    MeStatusView, MyPrivacyView,
    AdminQueueView,
    AdminActivityView,
    ChangeRequestRespondView,
    HeadRequestView,
    HeadRequestRespondView,
)

urlpatterns = [
    path('all/', MemberListView.as_view()),             # Admin: everyone | member: approved directory
    path('accept-reject/<int:pk>/', ApproveMemberView.as_view()),  # Admin
    path('add/', FamilyHeadAddMember.as_view()),       # Family head
    path('update/<int:member_id>/', FamilyHeadUpdateMember.as_view(), name='family-head-update-member'),
    path('delete/<int:member_id>/', FamilyHeadDeleteMember.as_view(), name='family-head-delete-member'),
    path('my-family/', MyFamilyMembers.as_view()),      # Logged user
    path('me/status/', MeStatusView.as_view()),
    path('me/privacy/', MyPrivacyView.as_view()),     # hide / show my number in the directory         # Approval state (call on every app start)
    path('<int:pk>/', MemberDetailView.as_view()),      # Detail + self/admin update
    path('tree/', FamilyTreeView.as_view()),            # Tree centred on the logged-in member
    path('tree/<int:pk>/', FamilyTreeView.as_view()),   # Tree centred on another member
    path('search/', MemberSearchView.as_view()),        # Search members
    path('relationship-requests/', RelationshipRequestView.as_view()),
    path('relationship-requests/<int:pk>/respond/', RelationshipRequestRespondView.as_view()),
    # admin review queues
    path('admin/queue/', AdminQueueView.as_view()),
    path('admin/activity/', AdminActivityView.as_view()),
    path('change-requests/<int:pk>/respond/', ChangeRequestRespondView.as_view()),
    # family head requests (new household / transfer headship)
    path('head-requests/', HeadRequestView.as_view()),
    path('head-requests/<int:pk>/respond/', HeadRequestRespondView.as_view()),
]
