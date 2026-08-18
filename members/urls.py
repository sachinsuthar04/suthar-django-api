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
    RelationshipRequestRespondView
)

urlpatterns = [
    path('all/', MemberListView.as_view()),             # Admin
    path('accept-reject/<int:pk>/', ApproveMemberView.as_view()),  # Admin
    path('add/', FamilyHeadAddMember.as_view()),       # Family head
    path( 'update/<int:member_id>/', FamilyHeadUpdateMember.as_view(), name='family-head-update-member'),
    path( 'delete/<int:member_id>/', FamilyHeadDeleteMember.as_view(), name='family-head-delete-member'),
    path('my-family/', MyFamilyMembers.as_view()),      # Logged user
    path('<int:pk>/', MemberDetailView.as_view()),      # Detail + Update
    path('tree/', FamilyTreeView.as_view()),            # Family tree
    path('search/', MemberSearchView.as_view()),        # Search members
    path('relationship-requests/', RelationshipRequestView.as_view()), # Get/Create requests
    path('relationship-requests/<int:pk>/respond/', RelationshipRequestRespondView.as_view()), # Accept/reject requests
]
