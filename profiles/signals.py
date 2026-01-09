# profiles/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from profiles.models import PersonalDetail, JobDetail, EducationDetail
from members.models import Member, MemberGender


# --------------------------------------------------
# Helper: Update Member(s) from Profile
# --------------------------------------------------
def update_member_from_profile(profile, data: dict):
    """
    One-way sync: Profile → Member
    Safe field-level sync
    """
    user = getattr(profile, "user", None)
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
            member.save(update_fields=updated_fields)


# --------------------------------------------------
# PersonalDetail → Member
# --------------------------------------------------
@receiver(post_save, sender=PersonalDetail)
def sync_personal_to_member(sender, instance, **kwargs):
    """
    Sync PersonalDetail changes to Member
    """
    gender_map = {
        "male": MemberGender.MALE,
        "female": MemberGender.FEMALE,
        "other": MemberGender.OTHER,
    }

    data = {
        "name": instance.full_name,
        "country_code": instance.country_code,
        "mobile": instance.phone,
        "email": instance.email,
        "date_of_birth": instance.dob,
        "native_place": instance.native_place,
        "status": instance.status,
    }

    # Gender mapping (SAFE)
    if instance.gender:
        data["gender"] = gender_map.get(
            instance.gender.lower(),
            MemberGender.OTHER
        )

    # Profile image (FILE ONLY, NOT URL)
    if instance.profile_image:
        data["profile_image"] = instance.profile_image

    update_member_from_profile(instance.profile, data)


# --------------------------------------------------
# JobDetail → Member
# --------------------------------------------------
@receiver(post_save, sender=JobDetail)
def sync_job_to_member(sender, instance, **kwargs):
    """
    Sync JobDetail changes to Member
    """
    if instance.occupation_type:
        update_member_from_profile(
            instance.profile,
            {"occupation": instance.occupation_type}
        )


# --------------------------------------------------
# EducationDetail → Member
# --------------------------------------------------
@receiver(post_save, sender=EducationDetail)
def sync_education_to_member(sender, instance, **kwargs):
    """
    Sync EducationDetail changes to Member
    """
    if instance.qualification:
        update_member_from_profile(
            instance.profile,
            {"highest_qualification": instance.qualification}
        )
