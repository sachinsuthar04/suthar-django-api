from django.test import TestCase

from members.testing import api, make_member


class MyPrivacy(TestCase):
    def test_member_can_hide_and_show_own_number(self):
        m = make_member("Me", login=True)
        c = api(m.user)
        r = c.patch("/api/members/me/privacy/", {"hideContact": True}, format="json")
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertTrue(m.hide_contact)
        self.assertTrue(c.get("/api/members/me/status/").json()["hideContact"])
        self.assertTrue(c.get("/api/members/me/privacy/").json()["hideContact"])
        c.patch("/api/members/me/privacy/", {"hideContact": False}, format="json")
        m.refresh_from_db()
        self.assertFalse(m.hide_contact)

    def test_rejects_non_boolean_and_anonymous(self):
        m = make_member("Me", login=True)
        self.assertEqual(api(m.user).patch("/api/members/me/privacy/", {"hideContact": "yes"}, format="json").status_code, 400)
        self.assertEqual(api().patch("/api/members/me/privacy/", {"hideContact": True}, format="json").status_code, 401)

    def test_only_changes_own_flag(self):
        mine = make_member("Me", login=True)
        other = make_member("Other", login=True)
        api(mine.user).patch("/api/members/me/privacy/", {"hideContact": True}, format="json")
        other.refresh_from_db()
        self.assertFalse(other.hide_contact)


class StatusDatesAndCommittee(TestCase):
    def test_status_returns_registration_date_and_committee_phone(self):
        from django.test import override_settings
        m = make_member("Me", login=True, status="pending")
        with override_settings(COMMITTEE_PHONE="+919800000000"):
            data = api(m.user).get("/api/members/me/status/").json()
        self.assertEqual(data["committeePhone"], "+919800000000")
        self.assertEqual(data["registeredOn"], m.created_at.date().isoformat())
        self.assertIn("decidedOn", data)
