from django.test import TestCase

from members.models import Member, MemberStatus
from members.testing import M, F, api, make_admin, make_family_with_head, make_member, make_user


class UnauthenticatedAndPendingAreBlocked(TestCase):
    ENDPOINTS = [
        "/api/members/all/", "/api/members/my-family/", "/api/members/tree/",
        "/api/members/search/?q=a", "/api/home/dashboard/", "/api/home/home-content/",
        "/api/community/events/", "/api/community/notices/", "/api/community/advertisements/",
        "/api/members/relationship-requests/", "/api/members/head-requests/",
    ]

    def setUp(self):
        self.pending = make_member("Pending", login=True, status=MemberStatus.PENDING)
        self.rejected = make_member("Rejected", login=True, status=MemberStatus.REJECTED)
        self.no_member = make_user()

    def test_anonymous_gets_401(self):
        for url in self.ENDPOINTS:
            self.assertEqual(api().get(url).status_code, 401, url)

    def test_pending_rejected_and_member_less_users_get_403(self):
        for user in (self.pending.user, self.rejected.user, self.no_member):
            client = api(user)
            for url in self.ENDPOINTS + [f"/api/members/{self.pending.id}/"]:
                self.assertEqual(client.get(url).status_code, 403, (user, url))

    def test_pending_user_may_still_use_status_notifications_and_villages(self):
        client = api(self.pending.user)
        self.assertEqual(client.get("/api/members/me/status/").status_code, 200)
        self.assertEqual(client.get("/api/notifications/my/").status_code, 200)
        self.assertEqual(client.get("/api/home/villages/").status_code, 200)

    def test_status_change_takes_effect_immediately_with_same_token(self):
        member = make_member("Soon", login=True, status=MemberStatus.ACTIVE)
        client = api(member.user)
        self.assertEqual(client.get("/api/members/my-family/").status_code, 200)
        member.status = MemberStatus.REJECTED
        member.save()
        self.assertEqual(client.get("/api/members/my-family/").status_code, 403)


class DirectoryAndPrivacy(TestCase):
    def setUp(self):
        self.family, self.head = make_family_with_head("Head")
        self.me = make_member("Me", login=True, family=self.family)
        self.other_family, self.other_head = make_family_with_head("Other Head")
        self.hidden = make_member("Hidden", login=True, family=self.other_family,
                                  hide_contact=True, email="h@x.com", address="secret")
        self.visible = make_member("Visible", login=True, family=self.other_family, email="v@x.com")
        self.pending = make_member("Pending", login=True, status=MemberStatus.PENDING)
        self.patel = make_member("Patel", login=True, community=2)
        self.no_login = make_member("NoLogin", family=self.other_family)
        self.admin = make_admin()

    def names(self, response):
        return {m["name"] for m in response.data["familyMembers"]}

    def test_member_directory_only_approved_same_community_with_login(self):
        names = self.names(api(self.me.user).get("/api/members/all/"))
        self.assertIn("Visible", names)
        self.assertNotIn("Pending", names)
        self.assertNotIn("Patel", names)        # other samaj
        self.assertNotIn("NoLogin", names)      # not a login yet

    def test_admin_sees_everyone_including_pending_and_no_login(self):
        names = self.names(api(self.admin).get("/api/members/all/"))
        self.assertTrue({"Pending", "Patel", "NoLogin", "Hidden"} <= names)

    def test_admin_can_filter_by_status(self):
        r = api(self.admin).get("/api/members/all/?status=pending")
        self.assertEqual(self.names(r), {"Pending"})

    def test_hide_contact_masks_phone_email_address_outside_household(self):
        rows = {m["name"]: m for m in api(self.me.user).get("/api/members/all/").data["familyMembers"]}
        self.assertIsNone(rows["Hidden"]["mobile"])
        self.assertIsNone(rows["Hidden"]["email"])
        self.assertIsNone(rows["Hidden"]["address"])
        self.assertEqual(rows["Visible"]["email"], "v@x.com")

    def test_hide_contact_not_applied_to_same_household_admin_or_self(self):
        same = make_member("Same", login=True, family=self.family, hide_contact=True, email="s@x.com")
        r = api(self.me.user).get(f"/api/members/{same.id}/")
        self.assertEqual(r.data["familyMembers"]["email"], "s@x.com")
        r = api(self.admin).get(f"/api/members/{self.hidden.id}/")
        self.assertEqual(r.data["familyMembers"]["email"], "h@x.com")
        r = api(self.hidden.user).get(f"/api/members/{self.hidden.id}/")
        self.assertEqual(r.data["familyMembers"]["email"], "h@x.com")

    def test_search_is_same_community_excludes_self_and_rejected(self):
        make_member("Visible Rejected", login=True, status=MemberStatus.REJECTED)
        r = api(self.me.user).get("/api/members/search/?q=Visible")
        names = {m["name"] for m in r.data["members"]}
        self.assertEqual(names, {"Visible"})
        r = api(self.me.user).get("/api/members/search/?q=Patel")
        self.assertEqual(r.data["members"], [])
        r = api(self.me.user).get("/api/members/search/?q=Me")
        self.assertNotIn("Me", {m["name"] for m in r.data["members"]})

    def test_detail_of_other_community_is_404(self):
        self.assertEqual(api(self.me.user).get(f"/api/members/{self.patel.id}/").status_code, 404)

    def test_family_listing_is_own_household_only(self):
        r = api(self.me.user).get("/api/members/my-family/")
        self.assertEqual(self.names(r), {"Head", "Me"})


class EditingOthersIsForbidden(TestCase):
    def setUp(self):
        self.family, self.head = make_family_with_head()
        self.me = make_member("Me", login=True, family=self.family)
        self.victim = make_member("Victim", login=True, city="Surat")
        self.admin = make_admin()

    def test_member_cannot_edit_someone_else(self):
        r = api(self.me.user).patch(f"/api/members/{self.victim.id}/", {"city": "Hacked"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.city, "Surat")

    def test_member_cannot_escalate_own_record(self):
        r = api(self.me.user).patch(
            f"/api/members/{self.me.id}/",
            {"role": "familyHead", "status": "active", "family": self.family.id,
             "community": 2, "city": "Rajkot"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.me.refresh_from_db()
        self.assertEqual(self.me.city, "Rajkot")          # allowed field
        self.assertEqual(self.me.role, "member")           # ignored
        self.assertEqual(self.me.community, 1)

    def test_self_key_field_edit_is_queued_not_applied(self):
        r = api(self.me.user).patch(f"/api/members/{self.me.id}/", {"name": "Renamed", "city": "Vapi"}, format="json")
        self.assertEqual(r.data["pending_review"], ["name"])
        self.me.refresh_from_db()
        self.assertEqual(self.me.name, "Me")
        self.assertEqual(self.me.city, "Vapi")

    def test_admin_can_edit_and_spouse_link_survives(self):
        wife = make_member("Wife", F, family=self.family, login=True)
        self.me.spouse = wife
        self.me.save()
        wife.spouse = self.me
        wife.save()
        r = api(self.admin).patch(f"/api/members/{self.me.id}/", {"city": "Admin City"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.me.refresh_from_db()
        wife.refresh_from_db()
        self.assertEqual(self.me.city, "Admin City")
        self.assertEqual(self.me.spouse_id, wife.id)       # regression: was silently unlinked
        self.assertEqual(wife.spouse_id, self.me.id)


class ContentPermissions(TestCase):
    PAYLOAD = {"title": "Diwali Milan", "description": "Come", "event_date": "2026-11-20"}

    def setUp(self):
        self.member = make_member("M", login=True)
        self.pending = make_member("P", login=True, status=MemberStatus.PENDING)
        self.admin = make_admin()

    def test_active_member_reads_but_cannot_write(self):
        c = api(self.member.user)
        self.assertEqual(c.get("/api/community/events/").status_code, 200)
        for url in ("events", "notices", "advertisements"):
            self.assertEqual(c.post(f"/api/community/{url}/", self.PAYLOAD, format="json").status_code, 403, url)

    def test_admin_can_create_edit_delete_and_notification_is_created(self):
        from community.models import Event
        from notifications.models import Notification
        c = api(self.admin)
        self.assertEqual(c.post("/api/community/events/", self.PAYLOAD, format="json").status_code, 201)
        event = Event.objects.get()
        self.assertTrue(Notification.objects.filter(type="event", reference_id=event.id).exists())
        self.assertIn(c.patch(f"/api/community/events/{event.id}/", {"title": "New"}, format="json").status_code, (200, 202))
        self.assertIn(c.delete(f"/api/community/events/{event.id}/").status_code, (200, 204))

    def test_member_cannot_delete_event(self):
        from community.models import Event
        e = Event.objects.create(title="x", description="y", created_by=self.admin)
        self.assertEqual(api(self.member.user).delete(f"/api/community/events/{e.id}/").status_code, 403)
        self.assertTrue(Event.objects.filter(id=e.id).exists())

    def test_pending_cannot_read(self):
        self.assertEqual(api(self.pending.user).get("/api/community/events/").status_code, 403)
