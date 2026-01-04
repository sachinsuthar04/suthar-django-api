from rest_framework import serializers
from members.constants import Community
from members.models import MemberStatus
from .models import UserProfile, PersonalDetail, EducationDetail, JobDetail


# ==================================================
# PERSONAL DETAILS
# ==================================================
from rest_framework import serializers
from members.constants import Community
from .models import UserProfile, PersonalDetail, EducationDetail, JobDetail


class PersonalDetailsSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source="full_name", required=False, allow_blank=True)
    nativePlace = serializers.CharField(source="native_place", required=False, allow_blank=True)
    currentCity = serializers.CharField(source="current_city", required=False, allow_blank=True, allow_null=True)
    profileImage = serializers.CharField(source="profile_image", required=False, allow_blank=True, allow_null=True)
    community = serializers.ChoiceField(choices=Community.choices, required=False, allow_null=True)
    # 🔒 READ-ONLY STATUS (ADMIN CONTROLLED)
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = PersonalDetail
        fields = [
            "fullName", "nickname", "gender", "dob", "email", "phone","country_code",
            "address", "nativePlace", "currentCity", "profileImage", "community","status",
        ]

class EducationDetailsSerializer(serializers.ModelSerializer):
    startYear = serializers.IntegerField(source="start_year", required=False, allow_null=True)
    endYear = serializers.IntegerField(source="end_year", required=False, allow_null=True)
    currentlyStudying = serializers.BooleanField(source="currently_studying", required=False)

    class Meta:
        model = EducationDetail
        fields = [
            "qualification",
            "institution",
            "field",
            "startYear",
            "endYear",
            "currentlyStudying",
        ]

    def to_representation(self, instance):
            """Return endYear as None if currentlyStudying is True"""
            data = super().to_representation(instance)
            if data.get("currentlyStudying") is True:
                data["endYear"] = None
            return data



class JobDetailsSerializer(serializers.ModelSerializer):
    occupationType = serializers.CharField(source="occupation_type", required=False, allow_blank=True, allow_null=True)
    companyName = serializers.CharField(source="company_name", required=False, allow_blank=True, allow_null=True)
    startDate = serializers.DateField(source="start_date", required=False, allow_null=True)
    incomeRange = serializers.CharField(source="income_range", required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = JobDetail
        fields = ["occupationType", "companyName", "role", "industry", "startDate", "incomeRange"]


class FullUserDetailsSerializer(serializers.Serializer):
    selectedRole = serializers.ChoiceField(
        choices=UserProfile.REGISTRATION_ROLE_CHOICES, required=False
    )
    personal = PersonalDetailsSerializer(required=False, default={})
    education = EducationDetailsSerializer(required=False, allow_null=True, default={})
    job = JobDetailsSerializer(required=False, allow_null=True, default={})

    def validate_selectedRole(self, value):
        if value and value not in dict(UserProfile.REGISTRATION_ROLE_CHOICES):
            raise serializers.ValidationError("Invalid role selected.")
        return value
