from django.db.models.signals import post_save
from django.dispatch import receiver
from members.models import Member
from profiles.models import UserProfile, PersonalDetail

@receiver(post_save, sender=Member)
def sync_member_to_userprofile(sender, instance, **kwargs):
    """
    Sync Member → UserProfile & PersonalDetail
    Triggered on:
    - API approval
    - Admin panel change
    """
    if not instance.user:
        return

    user = instance.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # ---------------------------
    # Sync ROLE
    # ---------------------------
    if instance.role and profile.registration_role != instance.role:
        profile.registration_role = instance.role
        profile.save(update_fields=["registration_role"])

    # ---------------------------
    # Sync PERSONAL DETAIL
    # ---------------------------
    personal, _ = PersonalDetail.objects.get_or_create(profile=profile)
    changed_fields = []

    if instance.name and personal.full_name != instance.name:
        personal.full_name = instance.name
        changed_fields.append("full_name")

    if instance.country_code and personal.country_code != instance.country_code:
            personal.country_code = instance.country_code
            changed_fields.append("country_code")

    if instance.mobile and personal.phone != instance.mobile:
        personal.phone = instance.mobile
        changed_fields.append("phone")

    if instance.native_place and personal.native_place != instance.native_place:
        personal.native_place = instance.native_place
        changed_fields.append("native_place")

    # ✅ IMPORTANT: SYNC STATUS
    if hasattr(personal, "status") and personal.status != instance.status:
        personal.status = instance.status
        changed_fields.append("status")

    if changed_fields:
        personal.save(update_fields=changed_fields)



def sync_member_to_profile_helper(member):
    if not member.user:
        return

    profile, _ = UserProfile.objects.get_or_create(user=member.user)
    personal, _ = PersonalDetail.objects.get_or_create(profile=profile)

    updated_fields = []

    if personal.status != member.status:
        personal.status = member.status
        updated_fields.append("status")

    if personal.country_code != member.country_code:
        personal.country_code = member.country_code
        updated_fields.append("country_code")

    if personal.phone != member.mobile:
        personal.phone = member.mobile
        updated_fields.append("phone")

    if updated_fields:
        personal._skip_member_sync = True
        personal.save(update_fields=updated_fields)

