"""
Key-field review + audit helpers.

Key identity fields of an APPROVED member are not edited directly: they are
queued as a ProfileChangeRequest and applied only when an admin accepts it.
"""
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from members.models import (
    AuditLog,
    Member,
    MemberStatus,
    ProfileChangeRequest,
    ReviewStatus,
)

KEY_FIELDS = ("name", "gender", "date_of_birth", "gotra")


def audit(actor, action, entity, entity_id=None, **data):
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        data=data,
    )


def _norm(field, value):
    if value in (None, ""):
        return None
    if field == "date_of_birth":
        if isinstance(value, date):
            return value.isoformat()
        parsed = parse_date(str(value))
        return parsed.isoformat() if parsed else str(value)
    if field == "gender":
        return str(value).strip().lower()
    return str(value).strip()


def review_required(member: Member) -> bool:
    """Only already-approved members go through review (new ones are reviewed
    as a whole at approval time)."""
    return bool(getattr(settings, "KEY_FIELD_REVIEW", True)) and member.status == MemberStatus.ACTIVE


def split_key_changes(member: Member, proposed: dict):
    """-> (applied_directly, queued_diff).  `proposed` is {field: new_value}."""
    direct, queued = {}, {}
    for field, new in proposed.items():
        if field not in KEY_FIELDS:
            direct[field] = new
            continue
        old_n, new_n = _norm(field, getattr(member, field)), _norm(field, new)
        if old_n == new_n:
            continue  # nothing changed
        if review_required(member):
            queued[field] = {"old": old_n, "new": new_n}
        else:
            direct[field] = new
    return direct, queued


@transaction.atomic
def queue_changes(member: Member, queued: dict, requested_by):
    """Create (or merge into) the member's pending change request."""
    if not queued:
        return None
    req = ProfileChangeRequest.objects.filter(
        member=member, status=ReviewStatus.PENDING
    ).first()
    if req:
        merged = dict(req.changes)
        for field, diff in queued.items():
            # keep the ORIGINAL old value, take the latest new value
            old = merged.get(field, {}).get("old", diff["old"])
            merged[field] = {"old": old, "new": diff["new"]}
        req.changes = merged
        req.requested_by = requested_by
        req.save(update_fields=["changes", "requested_by"])
    else:
        req = ProfileChangeRequest.objects.create(
            member=member, requested_by=requested_by, changes=queued
        )
    audit(requested_by, "profile_change_requested", "member", member.id, fields=list(queued))
    return req


def _notify(user, title, message, type_, ref_id):
    if not user:
        return
    from notifications.models import Notification

    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type=type_,
        reference_id=ref_id,
        reference_type="profile_change",
        action_date=timezone.now(),
    )


@transaction.atomic
def accept_change_request(req: ProfileChangeRequest, reviewer):
    member = req.member
    update_fields = []
    for field, diff in req.changes.items():
        new = diff["new"]
        if field == "date_of_birth":
            new = parse_date(new) if new else None
        setattr(member, field, new)
        update_fields.append(field)
    if update_fields:
        member.save(update_fields=update_fields)
        _sync_personal(member)

    req.status = ReviewStatus.ACCEPTED
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    audit(reviewer, "profile_change_accepted", "member", member.id, fields=update_fields)
    _notify(member.user, "Profile update approved",
            "Your profile changes were approved.", "profile_change", req.id)
    return req


@transaction.atomic
def reject_change_request(req: ProfileChangeRequest, reviewer, reason=None):
    req.status = ReviewStatus.REJECTED
    req.reason = reason
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save(update_fields=["status", "reason", "reviewed_by", "reviewed_at"])
    audit(reviewer, "profile_change_rejected", "member", req.member_id, reason=reason)
    _notify(req.member.user, "Profile update rejected",
            reason or "Your profile changes were rejected.", "profile_change", req.id)
    return req


def _sync_personal(member: Member):
    """Keep the legacy PersonalDetail row equal to the approved Member values."""
    if not member.user_id:
        return
    from profiles.models import PersonalDetail

    personal = PersonalDetail.objects.filter(profile__user_id=member.user_id).first()
    if not personal:
        return
    personal.full_name = member.name
    personal.gender = member.gender
    personal.dob = member.date_of_birth
    personal.save(update_fields=["full_name", "gender", "dob"])
