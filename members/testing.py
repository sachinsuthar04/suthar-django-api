"""Shared factories for the test-suite."""
import itertools

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from members.models import Family, Member, MemberGender, MemberRole, MemberStatus

User = get_user_model()
_phone = itertools.count(9000000000)


def next_phone():
    return str(next(_phone))


def make_user(phone=None):
    return User.objects.create_user(phone=phone or next_phone(), country_code="+91")


def make_admin(email="admin@example.com"):
    return User.objects.create_user(
        email=email, password="pass12345", role="admin", is_staff=True
    )


def make_member(
    name,
    gender=MemberGender.MALE,
    family=None,
    login=False,
    status=MemberStatus.ACTIVE,
    role=MemberRole.MEMBER,
    community=1,
    **kwargs,
):
    """Create a Member. login=True also creates the User and links it."""
    mobile = kwargs.pop("mobile", None) or next_phone()
    user = kwargs.pop("user", None)
    if login and user is None:
        user = make_user(mobile)
    return Member.objects.create(
        name=name,
        gender=gender,
        family=family,
        user=user,
        mobile=mobile,
        status=status,
        role=role,
        community=community,
        profile_completed=kwargs.pop("profile_completed", True),
        **kwargs,
    )


def make_family_with_head(head_name="Head", community=1):
    """Family + approved, logged-in head Member (the normal healthy state)."""
    head_member = make_member(
        head_name, login=True, role=MemberRole.FAMILY_HEAD, community=community
    )
    family = Family.objects.create(head=head_member.user)
    head_member.family = family
    head_member.save(update_fields=["family"])
    return family, head_member


def api(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


M, F = MemberGender.MALE, MemberGender.FEMALE
