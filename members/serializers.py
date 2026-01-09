from rest_framework import serializers
from django.db import transaction

from profiles.models import PersonalDetail
from .models import Member, MemberRole


# =====================================================
# 🔁 SHARED SPOUSE HANDLER (AUTO-LINK / AUTO-UNLINK)
# =====================================================
def handle_spouse_link(member: Member, spouse_id: int | None):
    """
    Bidirectional spouse link handler.
    - Auto-unlink old spouse
    - Auto-link new spouse
    """

    # 🧹 Remove existing spouse
    if member.spouse:
        old_spouse = member.spouse
        member.spouse = None
        old_spouse.spouse = None
        member.save(update_fields=["spouse"])
        old_spouse.save(update_fields=["spouse"])

    # ❌ If spouse_id is null → just unlink
    if not spouse_id:
        return

    try:
        spouse = Member.objects.select_for_update().get(id=spouse_id)
    except Member.DoesNotExist:
        raise serializers.ValidationError({"spouse_id": "Invalid spouse id"})

    # 🔐 Validations
    if spouse.id == member.id:
        raise serializers.ValidationError({"spouse_id": "Cannot assign self as spouse"})

    if spouse.family_id != member.family_id:
        raise serializers.ValidationError({"spouse_id": "Spouse must belong to same family"})

    if spouse.spouse:
        raise serializers.ValidationError({"spouse_id": "Selected spouse already linked"})

    # 🔁 Link both sides
    member.spouse = spouse
    spouse.spouse = member

    member.save(update_fields=["spouse"])
    spouse.save(update_fields=["spouse"])


# =====================================================
# MEMBER SERIALIZER (READ + UPDATE)
# =====================================================


class MemberSerializer(serializers.ModelSerializer):
    # -----------------------------
    # READ ONLY RELATIONS
    # -----------------------------
    family = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    # -----------------------------
    # DISPLAY FIELDS
    # -----------------------------
    family_id_display = serializers.ReadOnlyField(source="family_display_id")
    community_display = serializers.CharField(
        source="get_community_display",
        read_only=True
    )

    # -----------------------------
    # IMAGE (API-FRIENDLY)
    # -----------------------------
    profileImageUrl = serializers.SerializerMethodField()

    # -----------------------------
    # SAME KEY IN REQUEST & RESPONSE
    # -----------------------------
    spouse_id = serializers.SerializerMethodField()
    parent_id = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = "__all__"
        read_only_fields = (
            "family",
            "user",
            "created_at",
        )

    # -------------------------------------------------
    # IMAGE URL BUILDER
    # -------------------------------------------------
    def get_profileImageUrl(self, obj):
        request = self.context.get("request")

        if not obj.user:
             return None

        personal = PersonalDetail.objects.filter(
            profile__user=obj.user
        ).first()

        if personal and personal.profile_image:
            if request:
                return request.build_absolute_uri(personal.profile_image.url)
            return personal.profile_image.url

        return None

    # -------------------------------------------------
    # RELATION IDS
    # -------------------------------------------------
    def get_spouse_id(self, obj):
        return obj.spouse.id if obj.spouse else None

    def get_parent_id(self, obj):
        return obj.parent.id if obj.parent else None

    # -------------------------------------------------
    # UPDATE LOGIC
    # -------------------------------------------------
    def update(self, instance, validated_data):
        spouse_id = self.initial_data.get("spouse_id")
        parent_id = self.initial_data.get("parent_id")

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            # -------- SPOUSE LINK --------
            handle_spouse_link(instance, spouse_id)

            # -------- PARENT LINK --------
            if parent_id is not None:
                if int(parent_id) == instance.id:
                    raise serializers.ValidationError(
                        {"parent_id": "Cannot assign self as parent"}
                    )

                try:
                    parent_member = Member.objects.get(id=parent_id)
                    instance.parent = parent_member
                    instance.save(update_fields=["parent"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError(
                        {"parent_id": "Invalid parent id"}
                    )

        return instance

# =====================================================
# MEMBER CREATE SERIALIZER
# =====================================================
class MemberCreateSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=True)
    mobile = serializers.CharField(required=False, allow_blank=True)

    family = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    spouse_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True
    )
    parent_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True
    )

    class Meta:
        model = Member
        fields = (
            "mobile",
            "country_code",
            "name",
            "role",
            "relation",
            "gender",
            "date_of_birth",
            "email",
            "address",
            "city",
            "native_place",
            "profile_image",
            "occupation",
            "highest_qualification",
            "spouse_id",
            "parent_id",
            "family",
            "user",
        )

    def validate_role(self, value):
        family = self.context.get("family")
        if value == MemberRole.FAMILY_HEAD and family:
            if Member.objects.filter(
                family=family,
                role=MemberRole.FAMILY_HEAD
            ).exists():
                raise serializers.ValidationError(
                    "A Family Head already exists for this family."
                )
        return value

    def validate(self, attrs):
        attrs["mobile"] = (attrs.get("mobile") or "").strip() or None

        relation = (attrs.get("relation") or "").lower()
        if relation not in ["son", "daughter"] and not attrs.get("mobile"):
            raise serializers.ValidationError(
                {"mobile": "Mobile number is required for adult members"}
            )

        return attrs

    def create(self, validated_data):
        spouse_id = validated_data.pop("spouse_id", None)
        parent_id = validated_data.pop("parent_id", None)

        with transaction.atomic():
            member = super().create(validated_data)

            # Link parent if provided
            if parent_id:
                try:
                    parent_member = Member.objects.get(id=parent_id)
                    member.parent = parent_member
                    member.save(update_fields=["parent"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"parent_id": "Invalid parent id"})

            # Link spouse if provided
            handle_spouse_link(member, spouse_id)

        return member


# =====================================================
# MEMBER UPDATE SERIALIZER
# =====================================================
class MemberProfileUpdateSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=True)
    mobile = serializers.CharField(required=False, allow_blank=True)

    family = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    spouse_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True
    )
    parent_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True
    )

    class Meta:
        model = Member
        fields = (
            "mobile",
            "country_code",
            "name",
            "role",
            "relation",
            "gender",
            "date_of_birth",
            "email",
            "address",
            "city",
            "profile_image",
            "occupation",
            "highest_qualification",
            "spouse_id",
            "parent_id",
            "native_place",
            "family",
            "user",
        )

    def validate_role(self, value):
        if self.instance and value != self.instance.role:
            raise serializers.ValidationError("Role change is not allowed.")
        return value

   
    def validate(self, attrs):
        request = self.context.get("request")
        attrs["mobile"] = (attrs.get("mobile") or "").strip() or None

        if request and request.method == "PUT":
            required_fields = ["name", "role", "relation", "gender", "date_of_birth"]
            for field in required_fields:
                if not attrs.get(field):
                    raise serializers.ValidationError(
                        {field: "This field is required for a full update."}
                    )

            relation = (attrs.get("relation") or "").lower()
            if relation not in ["son", "daughter"] and not attrs.get("mobile"):
                raise serializers.ValidationError(
                    {"mobile": "Mobile number is required for adult members"}
                )

        return attrs

    def update(self, instance, validated_data):
        spouse_id = validated_data.pop("spouse_id", None)
        parent_id = validated_data.pop("parent_id", None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            # Update spouse
            handle_spouse_link(instance, spouse_id)

            # Update parent
            if parent_id is not None:
                if parent_id == instance.id:
                    raise serializers.ValidationError({"parent_id": "Cannot assign self as parent"})
                try:
                    parent_member = Member.objects.get(id=parent_id)
                    instance.parent = parent_member
                    instance.save(update_fields=["parent"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"parent_id": "Invalid parent id"})

        return instance
