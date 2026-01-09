from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from .models import Member, Family, MemberStatus


# ============================================================
# MEMBER INLINE (INSIDE FAMILY)
# ============================================================
class MemberInline(admin.TabularInline):
    model = Member
    fields = (
        "profile_preview",
        "name",
        "role",
        "mobile",
        "country_code",
        "status",
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def profile_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius:50%;" />',
                obj.profile_image.url,
            )
        return "-"
    profile_preview.short_description = "Image"


# ============================================================
# FAMILY ADMIN
# ============================================================
@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "head_user",
        "head_member_name",
        "member_count",
        "created_at",
    )
    search_fields = ("head__username",)
    inlines = [MemberInline]
    readonly_fields = ("head",)

    list_select_related = ("head",)

    def head_user(self, obj):
        return obj.head
    head_user.short_description = "Head User"

    def head_member_name(self, obj):
        member = Member.objects.filter(
            user=obj.head,
            role="familyHead",
        ).only("name").first()
        return member.name if member else "-"
    head_member_name.short_description = "Head Member"

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "Total Members"


# ============================================================
# MEMBER ADMIN
# ============================================================
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # --------------------------------------------------
    # LIST VIEW
    # --------------------------------------------------
    list_display = (
        "id",
        "profile_preview",
        "name",
        "mobile",
        "country_code",
        "community",
        "role",
        "status",
        "relation",
        "family_id_display",
        "family_head_name",
        "spouse_name",
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
        "country_code",
    )

    search_fields = (
        "name",
        "mobile",
        "email",
        "city",
        "country_code",
    )

    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "profile_completed",
        "spouse_id",
        "profile_preview",
    )

    list_select_related = (
        "family",
        "family__head",
        "spouse",
        "user",
    )

    # --------------------------------------------------
    # FIELDSETS
    # --------------------------------------------------
    fieldsets = (
        ("Basic Information", {
            "fields": (
                "user",
                "family",
                "community",
                "mobile",
                "country_code",
                "name",
                "role",
                "status",
                "relation",
            )
        }),
        ("Profile Details", {
            "fields": (
                "profile_preview",
                "profile_image",
                "gender",
                "date_of_birth",
                "email",
                "address",
                "city",
                "gotra",
                "native_place",
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

    # --------------------------------------------------
    # CUSTOM DISPLAY METHODS
    # --------------------------------------------------
    def profile_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="60" height="60" style="border-radius:50%;" />',
                obj.profile_image.url,
            )
        return "-"
    profile_preview.short_description = "Profile Image"

    def family_id_display(self, obj):
        return obj.family_display_id
    family_id_display.short_description = "Family ID"

    def family_head_name(self, obj):
        if obj.family and obj.family.head:
            head_member = Member.objects.filter(
                user=obj.family.head,
                role="familyHead",
            ).only("name").first()
            return head_member.name if head_member else "-"
        return "-"
    family_head_name.short_description = "Family Head"

    def spouse_name(self, obj):
        return obj.spouse.name if obj.spouse else "-"
    spouse_name.short_description = "Spouse"

    # --------------------------------------------------
    # ADMIN ACTIONS
    # --------------------------------------------------
    actions = ("approve_members", "make_family_head")

    @admin.action(description="Mark selected members as Approved / Active")
    def approve_members(self, request, queryset):
        updated = queryset.update(status=MemberStatus.ACTIVE)
        self.message_user(
            request,
            f"{updated} member(s) marked as ACTIVE.",
        )

    @admin.action(description="Make selected member as Family Head")
    def make_family_head(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Select exactly ONE member.",
                level="error",
            )
            return

        member = queryset.first()

        if not member.family:
            self.message_user(
                request,
                "Member does not belong to a family.",
                level="error",
            )
            return

        try:
            with transaction.atomic():
                member.make_family_head()

            self.message_user(
                request,
                f"{member.name} is now the Family Head.",
                level="success",
            )
        except Exception as e:
            self.message_user(request, str(e), level="error")
