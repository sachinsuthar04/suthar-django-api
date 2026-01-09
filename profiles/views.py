from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model

from members.constants import Community
from .models import UserProfile, PersonalDetail, EducationDetail, JobDetail
from members.models import Member, MemberGender, MemberStatus, MemberRole
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.get("data", request.data)

        # ---------- PROFILE ----------
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if "selectedRole" in data:
            profile.registration_role = data.get("selectedRole", "member")

        # ---------- PERSONAL ----------
        p_data = data.get("personal", {})
        personal, _ = PersonalDetail.objects.get_or_create(profile=profile)

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
            "status": "status",
        }

        for key, attr in personal_map.items():
            if key in p_data:
                setattr(personal, attr, p_data[key])

        # ---------- EDUCATION ----------
        e_data = data.get("education", {})
        education, _ = EducationDetail.objects.get_or_create(profile=profile)

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
        j_data = data.get("job", {})
        job, _ = JobDetail.objects.get_or_create(profile=profile)

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
        mandatory_fields = [
            personal.full_name,
            personal.native_place,
            personal.gender,
            personal.dob,
            personal.phone,
            profile.registration_role,
        ]

        profile.is_profile_completed = all(
            field not in (None, "", [])
            for field in mandatory_fields
        )

        # ---------- SAVE ----------
        profile.save()
        personal.save()
        education.save()
        job.save()

        # ---------- MEMBER SYNC ----------
        gender_map = {
            "male": MemberGender.MALE,
            "female": MemberGender.FEMALE,
            "other": MemberGender.OTHER,
        }

        Member.objects.update_or_create(
            user=request.user,
            defaults={
                "community": personal.community or Community.SUTHAR,
                "name": personal.full_name,
                "mobile": personal.phone,
                "country_code": personal.country_code,
                "gender": gender_map.get(
                    (personal.gender or "").lower(),
                    MemberGender.OTHER,
                ),
                "date_of_birth": personal.dob,
                "email": personal.email,
                "address": personal.address,
                "city": personal.current_city,
                "native_place": personal.native_place,

                # ✅ SYNC IMAGE HERE (ONLY)
                "profile_image": personal.profile_image,

                "occupation": job.occupation_type,
                "highest_qualification": education.qualification,
                "profile_completed": profile.is_profile_completed,
                "role": (
                    MemberRole.FAMILY_HEAD
                    if profile.registration_role == "familyHead"
                    else MemberRole.MEMBER
                ),
                "status": personal.status or MemberStatus.PENDING,
            },
        )

        return Response(
            {
                "success": True,
                "profileCompleted": profile.is_profile_completed,
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

        personal, _ = PersonalDetail.objects.get_or_create(
            profile__user=request.user
        )

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
