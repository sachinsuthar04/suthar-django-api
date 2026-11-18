"""One test for the whole real-life journey, through the real endpoints only:

new user -> OTP login -> registers as Family Head -> admin approves -> head adds
wife, son, father -> admin approves them -> son logs in with his own phone and is
linked to the existing record (no duplicate) -> each person sees the tree with
the relation names computed from their own point of view.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from members.models import Family, Member, MemberRole, MemberStatus
from members.testing import api, make_admin


def otp_login(phone):
    client = APIClient()
    r = client.post("/api/auth/verify-otp/", {"phone": phone, "country_code": "+91", "otp": "123456"}, format="json")
    assert r.status_code == 200, r.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['token']}")
    return client, r.data


def profile(phone, name, role, gender="male", dob="1975-01-01", village="Gadha"):
    return {
        "selectedRole": role,
        "personal": {
            "fullName": name, "gender": gender, "dob": dob, "phone": phone,
            "country_code": "+91", "nativePlace": village, "community": 1,
        },
    }


class FullUserJourney(TestCase):
    def test_register_head_add_family_login_and_tree(self):
        admin = api(make_admin())

        # 1. New user logs in with OTP, registers choosing "Family Head"
        head_phone = "9800000001"
        head, data = otp_login(head_phone)
        self.assertTrue(data["firstTime"])
        r = head.post("/api/profiles/profile/save/", profile(head_phone, "Ramesh Suthar", "familyHead"), format="json")
        self.assertIn(r.status_code, (200, 201), r.data)
        self.assertEqual(head.get("/api/members/me/status/").data["status"], "pending")
        # pending head can not add members yet
        self.assertNotEqual(head.post("/api/members/add/", {}, format="json").status_code, 201)

        # 2. Admin sees him in the queue and approves -> he becomes the one head of a new family
        queue = admin.get("/api/members/admin/queue/").data
        self.assertTrue(any(head_phone in str(x) for x in queue.values()), queue)
        me = Member.objects.get(mobile=head_phone)
        r = admin.post(f"/api/members/accept-reject/{me.id}/", {"status": "active"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        me.refresh_from_db()
        self.assertEqual((me.status, me.role), (MemberStatus.ACTIVE, MemberRole.FAMILY_HEAD))
        self.assertEqual(Family.objects.filter(head=me.user).count(), 1)

        # 3. Head adds wife, son (with his own phone) and his father
        son_phone = "9800000002"

        def add(**body):
            body.setdefault("country_code", "+91")
            r = head.post("/api/members/add/", body, format="json")
            self.assertEqual(r.status_code, 201, r.data)
            return Member.objects.get(id=r.data["member"]["id"])

        wife = add(name="Geeta Suthar", mobile="9800000003", relation="spouse", gender="female", date_of_birth="1978-02-02")
        son = add(name="Amit Suthar", mobile=son_phone, relation="son", gender="male", date_of_birth="2000-03-03")
        father = add(name="Mohan Suthar", mobile="9800000004", relation="father", gender="male", date_of_birth="1950-04-04")
        for m in (wife, son, father):
            self.assertEqual((m.status, m.family_id), (MemberStatus.PENDING, me.family_id))
            admin.post(f"/api/members/accept-reject/{m.id}/", {"status": "active"}, format="json")

        family = head.get("/api/members/my-family/")
        self.assertEqual(family.status_code, 200, family.data)
        self.assertEqual(Member.objects.filter(family_id=me.family_id).count(), 4)

        # 4. Son logs in with his own phone: linked to the record the head created, no duplicate,
        #    even if he wrongly picks "Family Head" he does not split the family
        son_client, data = otp_login(son_phone)
        son_client.post("/api/profiles/profile/save/", profile(son_phone, "Amit Suthar", "familyHead", dob="2000-03-03"), format="json")
        self.assertEqual(Member.objects.filter(mobile=son_phone).count(), 1)
        son.refresh_from_db()
        self.assertEqual((son.family_id, son.role), (me.family_id, MemberRole.MEMBER))
        self.assertEqual(Family.objects.count(), 1)
        self.assertEqual(son_client.get("/api/members/me/status/").data["status"], "active")

        # 5. Relations are computed per viewer
        def relations(client):
            r = client.get("/api/members/tree/")
            self.assertEqual(r.status_code, 200, r.data)
            return {n["name"]: n["relation_key"] for n in r.data["tree"]["nodes"]}

        head_view = relations(head)
        self.assertEqual(head_view["Ramesh Suthar"], "self")
        self.assertEqual(head_view["Geeta Suthar"], "wife")
        self.assertEqual(head_view["Amit Suthar"], "son")
        self.assertEqual(head_view["Mohan Suthar"], "father")

        son_view = relations(son_client)
        self.assertEqual(son_view["Amit Suthar"], "self")
        self.assertEqual(son_view["Ramesh Suthar"], "father")
        self.assertEqual(son_view["Geeta Suthar"], "mother")
        self.assertIn(son_view["Mohan Suthar"], ("grandfather", "paternal_grandfather"))
