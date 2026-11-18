from django.test import TestCase

from members.testing import api, make_member, make_user


class SaveFcmToken(TestCase):
    def test_saves_token_for_logged_in_user(self):
        user = make_user()
        r = api(user).post("/api/users/save-fcm-token/", {"token": "abc123"}, format="json")
        self.assertEqual(r.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.fcm_token, "abc123")

    def test_also_accepts_fcm_token_key_and_works_for_pending_members(self):
        member = make_member("P", login=True, status="pending")
        r = api(member.user).post("/api/users/save-fcm-token/", {"fcm_token": "xyz"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_requires_token_and_login(self):
        self.assertEqual(api(make_user()).post("/api/users/save-fcm-token/", {}, format="json").status_code, 400)
        self.assertEqual(api().post("/api/users/save-fcm-token/", {"token": "x"}, format="json").status_code, 401)

    def test_verify_otp_with_fcm_token_stores_it_and_does_not_crash(self):
        r = api().post("/api/auth/verify-otp/", {"phone": "9700000001", "country_code": "+91", "otp": "123456",
                                                 "fcm_token": "device-token"}, format="json")
        self.assertEqual(r.status_code, 200)
        from users.models import User
        self.assertEqual(User.objects.get(phone="9700000001").fcm_token, "device-token")
