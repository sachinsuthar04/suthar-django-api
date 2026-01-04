from django.contrib import admin
from django.db import transaction
from .models import Member, Family, MemberStatus

# ----------------------------
#   FAMILY ADMIN
# ----------------------------

class MemberInline(admin.TabularInline):
    model = Member
    fields = ("name", "role", "mobile", "country_code", "status")  # added country_code
    readonly_fields = ("name", "role", "mobile", "country_code", "status")  # added country_code
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "head_user",
        "head_member_name",
        "member_count",
        "created_at",
    )
    search_fields = ("head__username", "head__phone")
    inlines = [MemberInline]

    readonly_fields = ("head",)

    def head_user(self, obj):
        return obj.head
    head_user.short_description = "Head User"

    def head_member_name(self, obj):
        member = Member.objects.filter(
            user=obj.head,
            role="familyHead"
        ).first()
        return member.name if member else "-"
    head_member_name.short_description = "Head Member"

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "Total Members"


# ----------------------------
#   MEMBER ADMIN
# ----------------------------

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # ----------------------------
    # Display & Filters
    # ----------------------------
    list_display = (
        "id",
        "name",
        "mobile",
        "country_code",          # added
        "community",
        "role",
        "status",
        "relation",
        "family_id_display",
        "family_head_name",
        "city",
        "profile_completed",
        "created_at",
    )

    list_filter = (
        "community",
        "role",
        "status",
        "relation",
        "gender",
        "city",
        "profile_completed",
        "country_code",          # added
    )

    search_fields = (
        "name",
        "mobile",
        "email",
        "city",
        "country_code",          # added
    )

    ordering = ("-created_at",)
    readonly_fields = ("created_at", "profile_completed")

    # ----------------------------
    # Fieldsets
    # ----------------------------
    fieldsets = (
        ("Basic Information", {
            "fields": (
                "user",
                "family",
                "community",
                "mobile",
                "country_code",      # added
                "name",
                "role",
                "status",
                "relation",
            )
        }),
        ("Profile Details", {
            "fields": (
                "gender",
                "date_of_birth",
                "email",
                "address",
                "city",
                "gotra",
                "native_place",
                "profile_image",
            )
        }),
        ("Additional Details", {
            "fields": (
                "blood_group",
                "occupation",
                "highest_qualification",
                "spouse_id",
            )
        }),
        ("System Fields", {
            "fields": (
                "profile_completed",
                "created_at",
            )
        }),
    )

    # ----------------------------
    # Custom Methods
    # ----------------------------
    def family_id_display(self, obj):
        return obj.family.id if obj.family else "-"
    family_id_display.short_description = "Family ID"

    def family_head_name(self, obj):
        if obj.family and obj.family.head:
            user = obj.family.head
            if hasattr(user, "profile") and hasattr(user.profile, "full_name"):
                return user.profile.full_name
            return getattr(user, "username", getattr(user, "phone", str(user.id)))
        return "-"
    family_head_name.short_description = "Family Head"

    # ----------------------------
    # Admin Actions
    # ----------------------------
    actions = ["approve_members", "make_family_head"]

    @admin.action(description="Mark selected members as Approved / Active")
    def approve_members(self, request, queryset):
        for member in queryset:
            member.status = MemberStatus.ACTIVE
            member.save(update_fields=["status"])
            self.message_user(request, "Selected members have been activated.")

    @admin.action(description="Make selected member as Family Head")
    def make_family_head(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly ONE member to make Family Head.",
                level="error",
            )
            return

        member = queryset.first()

        if not member.family:
            self.message_user(
                request,
                "Selected member does not belong to a family.",
                level="error",
            )
            return

        try:
            member.make_family_head()
            self.message_user(
                request,
                f"{member.name} is now the Family Head.",
                level="success",
            )
        except Exception as e:
            self.message_user(request, str(e), level="error")
