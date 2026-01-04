from django.contrib.auth.backends import BaseBackend
from .models import User

class PhoneBackend(BaseBackend):
    """
    Authenticate using phone for members
    """
    def authenticate(self, request, phone=None, password=None, **kwargs):
        try:
            user = User.objects.get(phone=phone, role='member')
        except User.DoesNotExist:
            return None
        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
