from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from members.models import Member, MemberStatus, MemberRole, Family
from profiles.models import UserProfile
from members.constants import Community

User = get_user_model()

class Command(BaseCommand):
    help = "Sync UserProfiles and link all members to Family Head 9510981420"

    def handle(self, *args, **options):
        count_created = 0
        count_updated = 0
        
        # 1. Setup the Primary Family Head
        HEAD_MOBILE = "9510981420"
        try:
            head_user = User.objects.get(phone=HEAD_MOBILE)
            # Ensure a Family anchor exists for this specific head
            primary_family, _ = Family.objects.get_or_create(head=head_user)
            self.stdout.write(self.style.SUCCESS(f"Using Primary Family Head: {HEAD_MOBILE}"))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Critical Error: User with mobile {HEAD_MOBILE} not found!"))
            return

        role_mapping = {
            "familyHead": MemberRole.FAMILY_HEAD,
            "member": MemberRole.MEMBER,
        }

        # Get all profiles
        profiles = UserProfile.objects.select_related('user', 'personal', 'job').prefetch_related('educations')

        for profile in profiles:
            personal = getattr(profile, "personal", None)
            if not personal:
                continue

            job = getattr(profile, "job", None)
            educations = profile.educations.all()

            # Profile completion check
            mandatory_fields = [
                personal.full_name, personal.native_place, personal.gender, 
                personal.dob, personal.phone, profile.registration_role
            ]
            profile_completed = all(mandatory_fields)

            highest_qualification = None
            if educations.exists():
                highest_qualification = educations.order_by('-end_year').first().qualification

            with transaction.atomic():
                mapped_role = role_mapping.get(profile.registration_role, MemberRole.MEMBER)

                # --- TARGET LOGIC ---
                if profile.user.phone == HEAD_MOBILE:
                    # This is the actual head
                    current_family = primary_family
                    current_community = Community.SUTHAR
                elif mapped_role == MemberRole.MEMBER:
                    # Force all other 'members' to the primary family and community
                    current_family = primary_family
                    current_community = Community.SUTHAR
                else:
                    # For other 'familyHead' roles not matching the target phone, 
                    # create their own unique family anchor
                    current_family, _ = Family.objects.get_or_create(head=profile.user)
                    current_community = profile.community

                # --- SYNC MEMBER ---
                member, created = Member.objects.update_or_create(
                    user=profile.user,
                    defaults={
                        "name": personal.full_name,
                        "mobile": personal.phone,
                        "gender": personal.gender,
                        "date_of_birth": personal.dob,
                        "email": personal.email,
                        "address": personal.address,
                        "city": personal.current_city,
                        "native_place": personal.native_place,
                        "profile_image": personal.profile_image,
                        "occupation": job.occupation_type if job else None,
                        "highest_qualification": highest_qualification,
                        "profile_completed": profile_completed,
                        "status": MemberStatus.ACTIVE if profile_completed else MemberStatus.PENDING,
                        "role": mapped_role,
                        "family": current_family,
                        "community": current_community,
                    }
                )

                if created: count_created += 1
                else: count_updated += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Sync Finished. Members linked to {HEAD_MOBILE}."))