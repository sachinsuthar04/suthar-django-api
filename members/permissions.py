from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Member, MemberRole, MemberStatus


def is_app_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or getattr(user, "role", None) == "admin")
    )


def get_member(user):
    """The Member row of a login (first one if the data has duplicates)."""
    if not user or not user.is_authenticated:
        return None
    return Member.objects.filter(user=user).order_by("id").first()


def get_active_member(user):
    if not user or not user.is_authenticated:
        return None
    return Member.objects.filter(user=user, status=MemberStatus.ACTIVE).order_by("id").first()


class IsAppAdmin(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        return is_app_admin(request.user)


class IsActiveMember(BasePermission):
    """Admins, or logins whose membership has been approved by an admin.
    Pending / rejected / unknown users get 403 even with a valid token."""
    message = "Your membership is not active."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if is_app_admin(user):
            return True
        return Member.objects.filter(user=user, status=MemberStatus.ACTIVE).exists()


class IsFamilyHead(BasePermission):
    """Active family head (admins are NOT implicitly heads)."""
    message = "Only the family head can do this."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return Member.objects.filter(
            user=user, role=MemberRole.FAMILY_HEAD, status=MemberStatus.ACTIVE
        ).exists()


class AdminWriteActiveMemberRead(BasePermission):
    """Content (events, notices, ads): active members read, admins write."""
    message = "Only admins can modify this."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return IsActiveMember().has_permission(request, view)
        return is_app_admin(request.user)
