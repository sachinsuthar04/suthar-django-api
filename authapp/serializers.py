from rest_framework import serializers

class OTPSerializer(serializers.Serializer):
    country_code = serializers.CharField(
        max_length=5,
        required=False,
        default="+91",
        help_text="Country code like +91, +1"
    )
    phone = serializers.CharField(
        max_length=15,
        required=True,
        help_text="Phone number without country code"
    )

    def validate_country_code(self, value):
        value = value.strip()
        if not value.startswith("+") or not value[1:].isdigit():
            raise serializers.ValidationError("Invalid country code format")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("Phone must contain only digits")
        if len(value) < 6:
            raise serializers.ValidationError("Phone number is too short")
        return value

    def validate(self, data):
        """
        Optional combined value if needed elsewhere
        """
        data["full_phone"] = f"{data['country_code']}{data['phone']}"
        return data


class VerifyOTPSerializer(serializers.Serializer):
    country_code = serializers.CharField(
        max_length=5,
        required=False,
        default="+91"
    )
    phone = serializers.CharField(
        max_length=15,
        required=True
    )
    otp = serializers.CharField(
        max_length=6,
        required=True
    )
    fcm_token = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )

    def validate_country_code(self, value):
        value = value.strip()
        if not value.startswith("+") or not value[1:].isdigit():
            raise serializers.ValidationError("Invalid country code")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("Phone must contain only digits")
        if len(value) < 6:
            raise serializers.ValidationError("Invalid phone number")
        return value

    def validate_otp(self, value):
        value = value.strip()
        if not value.isdigit() or len(value) not in [4, 6]:
            raise serializers.ValidationError("OTP must be 4 or 6 digits")
        return value

    def validate(self, data):
        data["full_phone"] = f"{data['country_code']}{data['phone']}"
        return data
