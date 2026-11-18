from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from members.testing import api, make_admin, make_member


class Cors(TestCase):
    def test_preflight_is_answered_for_the_web_admin(self):
        r = APIClient().options(
            "/api/members/admin/queue/",
            HTTP_ORIGIN="http://localhost:5555",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "http://localhost:5555")
        self.assertIn("authorization", r["Access-Control-Allow-Headers"])
        self.assertIn("POST", r["Access-Control-Allow-Methods"])

    def test_any_requested_header_is_allowed_the_app_sends_prefer(self):
        r = APIClient().options(
            "/api/users/admin-login/",
            HTTP_ORIGIN="http://localhost:5555",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,prefer",
        )
        self.assertIn("prefer", r["Access-Control-Allow-Headers"])
        self.assertIn("content-type", r["Access-Control-Allow-Headers"])

    def test_normal_response_carries_the_header(self):
        r = APIClient().get("/swagger/", HTTP_ORIGIN="http://localhost:5555")
        self.assertEqual(r["Access-Control-Allow-Origin"], "http://localhost:5555")

    @override_settings(CORS_ALLOW_ALL=False, CORS_ALLOWED_ORIGINS=["https://admin.example.com"])
    def test_allow_list_blocks_other_origins(self):
        ok = APIClient().get("/swagger/", HTTP_ORIGIN="https://admin.example.com")
        bad = APIClient().get("/swagger/", HTTP_ORIGIN="https://evil.example")
        self.assertEqual(ok["Access-Control-Allow-Origin"], "https://admin.example.com")
        self.assertNotIn("Access-Control-Allow-Origin", bad)

    def test_no_origin_no_header(self):
        self.assertNotIn("Access-Control-Allow-Origin", APIClient().get("/swagger/"))


class AdminActivity(TestCase):
    def test_admin_sees_latest_decisions_members_do_not(self):
        admin = make_admin()
        m = make_member("New", login=True, status="pending")
        api(admin).post(f"/api/members/accept-reject/{m.id}/", {"status": "active"}, format="json")
        rows = api(admin).get("/api/members/admin/activity/").data["activity"]
        self.assertEqual(rows[0]["action"], "member_active")
        self.assertEqual(rows[0]["actor"], "admin@example.com")
        self.assertEqual(api(make_member("X", login=True).user).get("/api/members/admin/activity/").status_code, 403)
