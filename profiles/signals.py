# profiles/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from profiles.models import PersonalDetail, JobDetail, EducationDetail
from members.models import Member


# --------------------------------------------------
#   Helper: Update Member(s) from Profile
# --------------------------------------------------
def update_member_from_profile(profile, data: dict):
    """
    Sync Profile → Member
    Works for:
    - Multiple members per user
    - Partial updates
    - Prevents unnecessary saves
    """
    user = profile.user if profile else None
    if not user:
        return

    members = Member.objects.filter(user=user)
    if not members.exists():
        return

    for member in members:
        updated_fields = []

        for field, value in data.items():
            if value is not None and hasattr(member, field):
                if getattr(member, field) != value:
                    setattr(member, field, value)
                    updated_fields.append(field)

        if updated_fields:
            # 🔒 Prevent reverse signal loop
            member._skip_profile_sync = True
            member.save(update_fields=updated_fields)


# --------------------------------------------------
#   PersonalDetail → Member
# --------------------------------------------------
@receiver(post_save, sender=PersonalDetail)
def sync_personal_to_member(sender, instance, **kwargs):
    """
    Sync PersonalDetail changes to Member
    """
    # 🔒 Stop infinite loop
    if getattr(instance, "_skip_member_sync", False):
        return

    update_member_from_profile(
        instance.profile,
        {
            "name": instance.full_name,
            "country_code": instance.country_code,   # ✅ ADDED
            "mobile": instance.phone,
            "gender": instance.gender,
            "date_of_birth": instance.dob,
            "email": instance.email,
            "native_place": instance.native_place,
            "profile_image": instance.profile_image,
            "status": instance.status,
        }
    )


# --------------------------------------------------
#   JobDetail → Member
# --------------------------------------------------
@receiver(post_save, sender=JobDetail)
def sync_job_to_member(sender, instance, **kwargs):
    """
    Sync JobDetail changes to Member
    """
    update_member_from_profile(
        instance.profile,
        {
            "occupation": instance.occupation_type,
        }
    )


# --------------------------------------------------
#   EducationDetail → Member
# --------------------------------------------------
@receiver(post_save, sender=EducationDetail)
def sync_education_to_member(sender, instance, **kwargs):
    """
    Sync EducationDetail changes to Member
    """
    update_member_from_profile(
        instance.profile,
        {
            "highest_qualification": instance.qualification,
        }
    )
