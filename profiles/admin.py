from django.contrib import admin
from .models import (
    UserProfile,
    PersonalDetail,
    EducationDetail,
    JobDetail,
)

# ------------------------------------------------------------
# Inlines for a Unified User View
# ------------------------------------------------------------

class PersonalInline(admin.StackedInline):
    model = PersonalDetail
    extra = 0
    max_num = 1
    fields = (
        "full_name",
        "phone",
        "country_code",      # <-- Added field
        "nickname",
        "gender",
        "dob",
        "email",
        "address",
        "current_city",
        "native_place",
        "profile_image",
        "community",
        "status",
    )


class JobInline(admin.StackedInline):
    model = JobDetail
    extra = 0
    max_num = 1
    fields = (
        "occupation_type",
        "company_name",
        "role",
        "industry",
        "start_date",
        "income_range",
    )


class EducationInline(admin.TabularInline):
    model = EducationDetail
    extra = 0
    fields = (
        "qualification",
        "institution",
        "field",
        "start_year",
        "end_year",
        "currently_studying",
    )


# ------------------------------------------------------------
# Main Profile Admin
# ------------------------------------------------------------

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "get_name",
        "get_phone",
        "registration_role",
        "get_status",
        "get_community",
        "is_profile_completed",
    )

    list_filter = ("registration_role", "is_profile_completed")

    inlines = [
        PersonalInline,
        JobInline,
        EducationInline,
    ]

    # ----------------------------
    # Custom methods
    # ----------------------------
    def get_status(self, obj):
        if hasattr(obj, "personal") and obj.personal:
            return obj.personal.status
        return "-"
    get_status.short_description = "Status"

    def get_name(self, obj):
        if hasattr(obj, "personal") and obj.personal:
            return obj.personal.full_name
        return "-"
    get_name.short_description = "Name"

    def get_phone(self, obj):
        """
        Return phone with country code if available.
        Priority: personal.country_code > fallback '+91'
        """
        if hasattr(obj, "personal") and obj.personal:
            code = obj.personal.country_code or "+91"
            phone = obj.personal.phone or ""
            return f"{code} {phone}"
        elif hasattr(obj.user, "phone") and obj.user.phone:
            return obj.user.phone  # fallback to user.phone
        return "-"
    get_phone.short_description = "User Phone"

    def get_community(self, obj):
        if hasattr(obj, "personal") and obj.personal:
            return obj.personal.get_community_display()
        return "-"
    get_community.short_description = "Community"

    # ----------------------------
    # Fieldsets
    # ----------------------------
    fieldsets = (
        ("Account Info", {
            "fields": ("user", "registration_role", "is_profile_completed")
        }),
    )
