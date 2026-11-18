from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model

from members.constants import Community
from .models import UserProfile, PersonalDetail, EducationDetail, JobDetail
from members.models import Member, MemberGender, MemberStatus, MemberRole
from members.permissions import get_member, is_app_admin
from members.services.changes import audit, queue_changes, split_key_changes
from members.signals import sync_member_to_profile_helper
from members.services.households import request_new_household, HeadRequestError, validate_new_household
from rest_framework.parsers import MultiPartParser
from rest_framework.parsers import FormParser

User = get_user_model()

# ==================================================
# PROFILE DETAIL (GET)
# ==================================================

class ProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response(
                {"success": False, "message": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # own profile, an admin, or a member of the same family only
        if user.id != request.user.id and not is_app_admin(request.user):
            me = get_member(request.user)
            other = get_member(user)
            same_family = bool(me and other and me.family_id and me.family_id == other.family_id)
            if not (same_family and me.status == MemberStatus.ACTIVE):
                return Response(
                    {"success": False, "message": "Not allowed"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        profile = (
            UserProfile.objects
            .select_related("personal", "education_detail", "job")
            .filter(user=user)
            .first()
        )

        if not profile:
            profile = UserProfile.objects.create(user=user)

        personal = getattr(profile, "personal", None)
        education = getattr(profile, "education_detail", None)
        job = getattr(profile, "job", None)

        # Build profile image full URL
        profile_image_url = (
            request.build_absolute_uri(personal.profile_image.url)
            if personal and personal.profile_image else None
        )

        return Response(
            {
                "success": True,
                "data": {
                    "selectedRole": profile.registration_role or "member",
                    "personal": {
                        "fullName": personal.full_name if personal else "",
                        "nickname": personal.nickname if personal else "",
                        "gender": personal.gender if personal else "",
                        "dob": personal.dob.strftime("%Y-%m-%d") if personal and personal.dob else None,
                        "email": personal.email if personal else "",
                        "phone": personal.phone if personal else "",
                        "country_code": personal.country_code if personal else "",
                        "address": personal.address if personal else "",
                        "nativePlace": personal.native_place if personal else "",
                        "currentCity": personal.current_city if personal else "",
                        "profileImage": personal.profile_image.url if personal and personal.profile_image else "",
                        "profileImageUrl": profile_image_url,
                        "community": personal.community if personal and personal.community else None,
                        "status": personal.status if personal else MemberStatus.PENDING,
                    },
                    "education": {
                        "qualification": education.qualification if education else "",
                        "institution": education.institution if education else "",
                        "field": education.field if education else "",
                        "startYear": education.start_year if education else None,
                        "endYear": None if education and education.currently_studying else (education.end_year if education else None),
                        "currentlyStudying": education.currently_studying if education else False,
                    },
                    "job": {
                        "occupationType": job.occupation_type if job else "",
                        "companyName": job.company_name if job else "",
                        "role": job.role if job else "",
                        "industry": job.industry if job else "",
                        "startDate": job.start_date.strftime("%Y-%m-%d") if job and job.start_date else None,
                        "incomeRange": job.income_range if job else "",
                    },
                },
            },
            status=status.HTTP_200_OK,
        )



# ==================================================
# SAVE / UPDATE PROFILE (POST)
# ==================================================
class SaveUserProfileAPI(APIView):
    """
    Save / update the logged-in user's profile.

    Security rules (enforced HERE, never trusted from the client):
      * `status` is never taken from the request - approval is an admin decision
      * `role` is never taken from the request; asking for "familyHead" only
        creates a pending request that an admin approves together with the
        membership
      * key fields (name, gender, dob) of an already approved member are queued
        for admin review instead of being applied
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.get("data", request.data)
        user = request.user

        profile, _ = UserProfile.objects.get_or_create(user=user)
        personal, _ = PersonalDetail.objects.get_or_create(profile=profile)
        education, _ = EducationDetail.objects.get_or_create(profile=profile)
        job, _ = JobDetail.objects.get_or_create(profile=profile)

        member = get_member(user)
        wants_head = data.get("selectedRole") == "familyHead"

        # ---------- PERSONAL ----------
        p_data = data.get("personal", {}) or {}

        # key-field review for approved members
        queued = {}
        if member is not None:
            proposed = {}
            if "fullName" in p_data:
                proposed["name"] = p_data["fullName"]
            if "gender" in p_data:
                proposed["gender"] = p_data["gender"]
            if "dob" in p_data:
                proposed["date_of_birth"] = p_data["dob"]
            _, queued = split_key_changes(member, proposed)
        skip_personal = set()
        if "name" in queued:
            skip_personal.add("fullName")
        if "gender" in queued:
            skip_personal.add("gender")
        if "date_of_birth" in queued:
            skip_personal.add("dob")

        personal_map = {
            "fullName": "full_name",
            "nickname": "nickname",
            "gender": "gender",
            "dob": "dob",
            "email": "email",
            "phone": "phone",
            "country_code": "country_code",
            "address": "address",
            "nativePlace": "native_place",
            "currentCity": "current_city",
            "community": "community",
            # "status" intentionally absent
        }
        for key, attr in personal_map.items():
            if key in p_data and key not in skip_personal:
                setattr(personal, attr, p_data[key])

        # ---------- EDUCATION ----------
        e_data = data.get("education", {}) or {}
        for key, attr in {
            "qualification": "qualification",
            "institution": "institution",
            "field": "field",
            "startYear": "start_year",
            "endYear": "end_year",
            "currentlyStudying": "currently_studying",
        }.items():
            if key in e_data:
                setattr(education, attr, e_data[key])

        # ---------- JOB ----------
        j_data = data.get("job", {}) or {}
        for key, attr in {
            "occupationType": "occupation_type",
            "companyName": "company_name",
            "role": "role",
            "industry": "industry",
            "startDate": "start_date",
            "incomeRange": "income_range",
        }.items():
            if key in j_data:
                setattr(job, attr, j_data[key])

        # ---------- PROFILE COMPLETION ----------
        # (queued key fields are still "filled": the approved value counts)
        mandatory_fields = [
            personal.full_name or (member.name if member else None),
            personal.native_place,
            personal.gender or (member.gender if member else None),
            personal.dob or (member.date_of_birth if member else None),
            personal.phone,
        ]
        profile_completed = all(f not in (None, "", []) for f in mandatory_fields)
        profile.is_profile_completed = profile_completed

        # ---------- SAVE ----------
        profile.save()
        personal.save()
        education.save()
        job.save()

        # ---------- MEMBER (single source of approval truth) ----------
        gender_map = {
            "male": MemberGender.MALE,
            "female": MemberGender.FEMALE,
            "other": MemberGender.OTHER,
        }
        common = {
            "email": personal.email,
            "address": personal.address,
            "city": personal.current_city,
            "native_place": personal.native_place,
            "profile_image": personal.profile_image,
            "occupation": job.occupation_type,
            "highest_qualification": education.qualification,
            "profile_completed": profile_completed,
        }

        if member is None:
            member = Member.objects.create(
                user=user,
                community=personal.community or Community.SUTHAR,
                name=personal.full_name,
                mobile=personal.phone,
                country_code=personal.country_code,
                gender=gender_map.get((personal.gender or "").lower(), MemberGender.OTHER),
                date_of_birth=personal.dob,
                role=MemberRole.MEMBER,          # never from the client
                status=MemberStatus.PENDING,     # never from the client
                **common,
            )
        else:
            for field, value in common.items():
                setattr(member, field, value)
            if not member.community:
                member.community = personal.community or Community.SUTHAR
            # key fields that are NOT queued are applied directly
            if "name" not in queued:
                member.name = personal.full_name or member.name
            if "gender" not in queued and personal.gender:
                member.gender = gender_map.get(personal.gender.lower(), MemberGender.OTHER)
            if "date_of_birth" not in queued and personal.dob:
                member.date_of_birth = personal.dob
            member.save()
            if queued:
                queue_changes(member, queued, user)

        # ---------- "Edit and resend": a rejected member who fixes the profile
        # goes back into the review queue (the reason stays in the audit log) ----------
        resubmitted = False
        if member.status == MemberStatus.REJECTED and profile_completed:
            old_reason = member.status_reason
            member.status = MemberStatus.PENDING
            member.status_reason = None
            member.save(update_fields=["status", "status_reason"])
            sync_member_to_profile_helper(member)
            audit(user, "member_resubmitted", "member", member.id, previous_reason=old_reason)
            resubmitted = True

        # ---------- FAMILY HEAD REQUEST ----------
        head_request_pending = False
        if wants_head and member.role != MemberRole.FAMILY_HEAD and member.family_id is None:
            try:
                validate_new_household(member)
                request_new_household(member, user)
                head_request_pending = True
            except HeadRequestError:
                pass

        # profile role mirrors the real role, not the requested one
        real_role = "familyHead" if member.role == MemberRole.FAMILY_HEAD else "member"
        if profile.registration_role != real_role:
            profile.registration_role = real_role
            profile.save(update_fields=["registration_role"])

        return Response(
            {
                "success": True,
                "profileCompleted": profile_completed,
                "status": member.status,
                "pendingReview": sorted(queued),
                "headRequestPending": head_request_pending,
                "resubmitted": resubmitted,
                "message": "Profile saved successfully",
            },
            status=status.HTTP_200_OK,
        )



class UploadProfileImageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"success": False, "message": "File not provided"},
                status=400,
            )

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        personal, _ = PersonalDetail.objects.get_or_create(profile=profile)

        personal.profile_image = file
        personal.save()

        return Response(
            {
                "success": True,
                "profileImageUrl": request.build_absolute_uri(
                    personal.profile_image.url
                ),
            },
            status=200,
        )
