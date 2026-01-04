from rest_framework import serializers
from .models import (
    Member,
    Family,
    MemberRole,
    MemberStatus,
    Community,
)


# -------------------------
# Member Serializer (Full)
# -------------------------
class MemberSerializer(serializers.ModelSerializer):
    # Expose only family ID, not the whole object
    family = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    # Display helpers
    family_id_display = serializers.ReadOnlyField(source="family_display_id")
    community_display = serializers.CharField(
        source="get_community_display",
        read_only=True
    )

    class Meta:
        model = Member
        fields = "__all__"


# -------------------------
# Member Create Serializer
# -------------------------
class MemberCreateSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=True)
    mobile = serializers.CharField(required=False, allow_blank=True)
    family = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Member
        # ❌ family, community, status are backend-controlled
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
            "family",
            "user",
        )

    # 🔐 Prevent creating another Family Head
    def validate_role(self, value):
        if value == MemberRole.FAMILY_HEAD:
            family = self.context.get("family")
            if family and Member.objects.filter(family=family, role=MemberRole.FAMILY_HEAD).exists():
                raise serializers.ValidationError("A Family Head already exists for this family.")
        return value

    def validate(self, attrs):
        # Normalize empty mobile → None
        attrs["mobile"] = (attrs.get("mobile") or "").strip() or None

        relation = (attrs.get("relation") or "").lower()
        mobile = attrs.get("mobile")
        if relation not in ["son", "daughter"] and not mobile:
            raise serializers.ValidationError(
                {"mobile": "Mobile number is required for adult members"}
            )

        return attrs


# -------------------------
# Member Update Serializer
# -------------------------
class MemberProfileUpdateSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=True)
    mobile = serializers.CharField(required=False, allow_blank=True)
    family = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

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
            "native_place",
            "family",
            "user",
        )

    # 🔐 Prevent role change via API
    def validate_role(self, value):
        if self.instance and value != self.instance.role:
            raise serializers.ValidationError("Role change is not allowed.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")

        # Normalize empty mobile → None
        attrs["mobile"] = (attrs.get("mobile") or "").strip() or None

        # PUT = full update → enforce required fields
        if request and request.method == "PUT":
            required_fields = [
                "name",
                "role",
                "relation",
                "gender",
                "date_of_birth",
            ]

            for field in required_fields:
                value = attrs.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    raise serializers.ValidationError(
                        {field: "This field is required for a full update."}
                    )

            # Mobile rule for adults
            relation = (attrs.get("relation") or "").lower()
            mobile = attrs.get("mobile")
            if relation not in ["son", "daughter"] and not mobile:
                raise serializers.ValidationError(
                    {"mobile": "Mobile number is required for adult members"}
                )

        return attrs
