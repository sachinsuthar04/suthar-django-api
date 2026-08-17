from rest_framework import serializers
from django.db import transaction

from profiles.models import PersonalDetail
from .models import Member, MemberRole
from collections import deque

def check_circular_dependency(member_id, new_parent_id):
    if not member_id or not new_parent_id:
        return False
    if member_id == new_parent_id:
        return True
        
    queue = deque([new_parent_id])
    visited = set()
    
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        
        if current == member_id:
            return True
            
        try:
            m = Member.objects.get(id=current)
            if m.father_id:
                queue.append(m.father_id)
            if m.mother_id:
                queue.append(m.mother_id)
        except Member.DoesNotExist:
            continue
            
    return False


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
    father_id = serializers.SerializerMethodField()
    mother_id = serializers.SerializerMethodField()

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

    def get_father_id(self, obj):
        return obj.father.id if obj.father else None

    def get_mother_id(self, obj):
        return obj.mother.id if obj.mother else None

    # -------------------------------------------------
    # UPDATE LOGIC
    # -------------------------------------------------
    def update(self, instance, validated_data):
        spouse_id = self.initial_data.get("spouse_id")
        father_id = self.initial_data.get("father_id")
        mother_id = self.initial_data.get("mother_id")

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            # -------- SPOUSE LINK --------
            handle_spouse_link(instance, spouse_id)

            # -------- FATHER LINK --------
            if father_id is not None:
                if int(father_id) == instance.id:
                    raise serializers.ValidationError({"father_id": "Cannot assign self as father"})
                if check_circular_dependency(instance.id, int(father_id)):
                    raise serializers.ValidationError({"father_id": "Circular dependency detected. Cannot assign this member as father."})
                try:
                    father_member = Member.objects.get(id=father_id)
                    instance.father = father_member
                    instance.save(update_fields=["father"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"father_id": "Invalid father id"})
                    
            # -------- MOTHER LINK --------
            if mother_id is not None:
                if int(mother_id) == instance.id:
                    raise serializers.ValidationError({"mother_id": "Cannot assign self as mother"})
                if check_circular_dependency(instance.id, int(mother_id)):
                    raise serializers.ValidationError({"mother_id": "Circular dependency detected. Cannot assign this member as mother."})
                try:
                    mother_member = Member.objects.get(id=mother_id)
                    instance.mother = mother_member
                    instance.save(update_fields=["mother"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"mother_id": "Invalid mother id"})

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
    father_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    mother_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

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
            "father_id",
            "mother_id",
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
        father_id = validated_data.pop("father_id", None)
        mother_id = validated_data.pop("mother_id", None)
        parent_id = self.initial_data.get("parent_id", None)
        relation = (validated_data.get("relation") or "").lower()

        with transaction.atomic():
            member = super().create(validated_data)

            # Link father if provided
            if father_id:
                try:
                    father_member = Member.objects.get(id=father_id)
                    member.father = father_member
                    member.save(update_fields=["father"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"father_id": "Invalid father id"})

            # Link mother if provided
            if mother_id:
                try:
                    mother_member = Member.objects.get(id=mother_id)
                    member.mother = mother_member
                    member.save(update_fields=["mother"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"mother_id": "Invalid mother id"})

            # Handle legacy parent_id from Flutter
            if parent_id:
                try:
                    parent_member = Member.objects.get(id=parent_id)
                    if parent_member.gender == 'female':
                        member.mother = parent_member
                        member.save(update_fields=["mother"])
                    else:
                        member.father = parent_member
                        member.save(update_fields=["father"])
                except Member.DoesNotExist:
                    pass

            # Handle backward linking based on relation
            request = self.context.get("request")
            if request and hasattr(request, "user") and request.user.is_authenticated:
                creator = Member.objects.filter(user=request.user).first()
                if creator:
                    if relation == "father":
                        if check_circular_dependency(creator.id, member.id):
                            raise serializers.ValidationError({"father_id": "Circular dependency"})
                        creator.father = member
                        creator.save(update_fields=["father"])
                    elif relation == "mother":
                        if check_circular_dependency(creator.id, member.id):
                            raise serializers.ValidationError({"mother_id": "Circular dependency"})
                        creator.mother = member
                        creator.save(update_fields=["mother"])
                    elif relation == "spouse":
                        handle_spouse_link(creator, member.id)

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
    father_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    mother_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

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
            "father_id",
            "mother_id",
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
        father_id = validated_data.pop("father_id", None)
        mother_id = validated_data.pop("mother_id", None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            # Update spouse
            handle_spouse_link(instance, spouse_id)

            # Update father
            if father_id is not None:
                if father_id == instance.id:
                    raise serializers.ValidationError({"father_id": "Cannot assign self as father"})
                if check_circular_dependency(instance.id, father_id):
                    raise serializers.ValidationError({"father_id": "Circular dependency detected. Cannot assign this member as father."})
                try:
                    father_member = Member.objects.get(id=father_id)
                    instance.father = father_member
                    instance.save(update_fields=["father"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"father_id": "Invalid father id"})

            # Update mother
            if mother_id is not None:
                if mother_id == instance.id:
                    raise serializers.ValidationError({"mother_id": "Cannot assign self as mother"})
                if check_circular_dependency(instance.id, mother_id):
                    raise serializers.ValidationError({"mother_id": "Circular dependency detected. Cannot assign this member as mother."})
                try:
                    mother_member = Member.objects.get(id=mother_id)
                    instance.mother = mother_member
                    instance.save(update_fields=["mother"])
                except Member.DoesNotExist:
                    raise serializers.ValidationError({"mother_id": "Invalid mother id"})

        return instance
