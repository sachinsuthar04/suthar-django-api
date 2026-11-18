"""Family-head requests: new household / transfer of headship."""
from django.db import transaction
from django.utils import timezone

from members.models import (
    Family,
    FamilyHeadRequest,
    HeadRequestKind,
    Member,
    MemberRole,
    MemberStatus,
    ReviewStatus,
)
from members.services.changes import audit


class HeadRequestError(Exception):
    pass


def _notify(user, title, message):
    if not user:
        return
    from notifications.models import Notification

    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type="head_request",
        reference_type="head_request",
        action_date=timezone.now(),
    )


def validate_new_household(member: Member):
    if not member.user_id:
        raise HeadRequestError("Family head must be linked to a login.")
    if member.role == MemberRole.FAMILY_HEAD:
        raise HeadRequestError("Member is already a family head.")
    if Family.objects.filter(head_id=member.user_id).exists():
        raise HeadRequestError("This login already heads a family.")


def validate_transfer(req: FamilyHeadRequest):
    member, family = req.member, req.family
    if not family or member.family_id != family.id:
        raise HeadRequestError("New head must belong to the family.")
    if not member.user_id:
        raise HeadRequestError("New head must be linked to a login.")
    if member.status != MemberStatus.ACTIVE:
        raise HeadRequestError("New head must be an approved member.")
    if Family.objects.filter(head_id=member.user_id).exclude(id=family.id).exists():
        raise HeadRequestError("This login already heads another family.")


@transaction.atomic
def approve_head_request(req: FamilyHeadRequest, reviewer):
    if req.status != ReviewStatus.PENDING:
        raise HeadRequestError("Request already processed.")
    member = req.member

    if req.kind == HeadRequestKind.NEW_HOUSEHOLD:
        validate_new_household(member)
        family = Family.objects.create(head=member.user)
        member.family = family
        member.role = MemberRole.FAMILY_HEAD
        member.save(update_fields=["family", "role"])
    else:
        validate_transfer(req)
        member.make_family_head()

    req.status = ReviewStatus.ACCEPTED
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    audit(reviewer, "head_request_accepted", "member", member.id, kind=req.kind)
    _notify(member.user, "You are now the family head",
            "Your family head request was approved.")
    return req


@transaction.atomic
def reject_head_request(req: FamilyHeadRequest, reviewer, reason=None):
    if req.status != ReviewStatus.PENDING:
        raise HeadRequestError("Request already processed.")
    req.status = ReviewStatus.REJECTED
    req.reason = reason
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save(update_fields=["status", "reason", "reviewed_by", "reviewed_at"])
    audit(reviewer, "head_request_rejected", "member", req.member_id, kind=req.kind, reason=reason)
    _notify(req.member.user, "Family head request rejected", reason or "Your request was rejected.")
    return req


def request_new_household(member: Member, requested_by, note=None):
    """Create (idempotent) a pending NEW_HOUSEHOLD request."""
    req, created = FamilyHeadRequest.objects.get_or_create(
        member=member,
        kind=HeadRequestKind.NEW_HOUSEHOLD,
        status=ReviewStatus.PENDING,
        defaults={"requested_by": requested_by, "note": note, "family": member.family},
    )
    if created:
        audit(requested_by, "head_request_created", "member", member.id, kind=req.kind)
    return req, created
