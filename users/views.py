from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User

class AdminLoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            user = User.objects.get(email=email, role='admin')
        except User.DoesNotExist:
            return Response({"success": False, "message": "Admin not found"}, status=404)

        if not user.check_password(password):
            return Response({"success": False, "message": "Incorrect password"}, status=400)

        refresh = RefreshToken.for_user(user)
        return Response({
            "success": True,
            "token": str(refresh.access_token),
            "user": {"id": user.id, "email": user.email, "role": user.role}
        })


class MemberLoginView(APIView):
    def post(self, request):
        phone = request.data.get('phone')
        try:
            user = User.objects.get(phone=phone, role='member')
        except User.DoesNotExist:
            # Optionally create user automatically
            user = User.objects.create_user(phone=phone, role='member')

        # Here you send OTP to user.phone
        # Return a temporary token for verification (or skip if OTP handled separately)
        return Response({
            "success": True,
            "message": "OTP sent to phone",
            "user": {"id": user.id, "phone": user.phone}
        })


class SaveFcmTokenView(APIView):
    """Store the device push token of the logged-in user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get("token") or request.data.get("fcm_token") or "").strip()
        if not token:
            return Response({"success": False, "message": "token is required"}, status=400)
        request.user.fcm_token = token
        request.user.save(update_fields=["fcm_token"])
        return Response({"success": True, "message": "Token saved"})
