from django.contrib import admin
from django.utils.html import format_html

from .models import (
    UserProfile,
    PersonalDetail,
    EducationDetail,
    JobDetail,
)


# ============================================================
# PERSONAL DETAIL INLINE
# ============================================================
class PersonalInline(admin.StackedInline):
    model = PersonalDetail
    extra = 0
    max_num = 1

    readonly_fields = ("profile_preview",)

    fields = (
        "profile_preview",
        "full_name",
        "phone",
        "country_code",
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

    def profile_preview(self, obj):
        if obj and obj.profile_image:
            return format_html(
                '<img src="{}" width="80" height="80" style="border-radius:50%;" />',
                obj.profile_image.url,
            )
        return "-"
    profile_preview.short_description = "Profile Image"


# ============================================================
# JOB DETAIL INLINE
# ============================================================
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


# ============================================================
# EDUCATION DETAIL INLINE
# ============================================================
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


# ============================================================
# USER PROFILE ADMIN
# ============================================================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    # --------------------------------------------------
    # LIST VIEW
    # --------------------------------------------------
    list_display = (
        "id",
        "profile_image_preview",
        "get_name",
        "get_phone",
        "registration_role",
        "get_status",
        "get_community",
        "is_profile_completed",
    )

    list_filter = (
        "registration_role",
        "is_profile_completed",
    )

    search_fields = (
        "user__phone",
        "personal__full_name",
        "personal__email",
    )

    list_select_related = ("user",)
    inlines = (PersonalInline, JobInline, EducationInline)

    # --------------------------------------------------
    # FIELDSETS
    # --------------------------------------------------
    fieldsets = (
        ("Account Info", {
            "fields": (
                "user",
                "registration_role",
                "is_profile_completed",
            )
        }),
    )

    readonly_fields = ("profile_image_preview",)

    # --------------------------------------------------
    # CUSTOM DISPLAY METHODS
    # --------------------------------------------------
    def profile_image_preview(self, obj):
        if hasattr(obj, "personal") and obj.personal and obj.personal.profile_image:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius:50%;" />',
                obj.personal.profile_image.url,
            )
        return "-"
    profile_image_preview.short_description = "Image"

    def get_status(self, obj):
        return getattr(obj.personal, "status", "-")
    get_status.short_description = "Status"

    def get_name(self, obj):
        return getattr(obj.personal, "full_name", "-")
    get_name.short_description = "Name"

    def get_phone(self, obj):
        """
        Phone priority:
        1. PersonalDetail (country_code + phone)
        2. User.phone
        """
        if hasattr(obj, "personal") and obj.personal:
            code = obj.personal.country_code or "+91"
            phone = obj.personal.phone or ""
            if phone:
                return f"{code} {phone}"

        return getattr(obj.user, "phone", "-")
    get_phone.short_description = "Phone"

    def get_community(self, obj):
        if hasattr(obj, "personal") and obj.personal:
            return obj.personal.get_community_display()
        return "-"
    get_community.short_description = "Community"
