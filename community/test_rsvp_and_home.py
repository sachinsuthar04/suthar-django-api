from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone

from community.models import Advertisement, Event, EventRSVP, Notice
from members.testing import F, M, api, make_admin, make_family_with_head, make_member
from notifications.models import Notification


def make_event(admin, title="Samuh Lagna Samaroh", days=10, **kw):
    return Event.objects.create(
        title=title, description="d", created_by=admin,
        event_date=date.today() + timedelta(days=days), event_time=time(9, 0), location="Samaj Wadi, Idar", **kw,
    )


class Rsvp(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.event = make_event(self.admin)
        self.family, self.head = make_family_with_head("Head")
        self.wife = make_member("Wife", F, family=self.family, login=True)
        self.other_family, self.other_head = make_family_with_head("Other")

    def rsvp(self, user, **body):
        return api(user).post(f"/api/community/events/{self.event.id}/rsvp/", body, format="json")

    def test_member_says_going_and_it_is_idempotent(self):
        r = self.rsvp(self.head.user, going=True)
        self.assertEqual((r.status_code, r.data["going"], r.data["goingCount"]), (200, True, 1))
        r = self.rsvp(self.head.user, going=True)
        self.assertEqual((r.data["going"], r.data["goingCount"]), (True, 1))
        self.assertEqual(EventRSVP.objects.count(), 1)

    def test_toggle_when_no_value_given(self):
        self.assertTrue(self.rsvp(self.head.user).data["going"])
        self.assertFalse(self.rsvp(self.head.user).data["going"])
        self.assertEqual(EventRSVP.objects.count(), 0)

    def test_cancel(self):
        self.rsvp(self.head.user, going=True)
        r = self.rsvp(self.head.user, going=False)
        self.assertEqual((r.data["going"], r.data["goingCount"]), (False, 0))

    def test_count_is_per_family_not_per_person(self):
        self.rsvp(self.head.user, going=True)
        self.rsvp(self.wife.user, going=True)          # same household
        r = self.rsvp(self.other_head.user, going=True)  # other household
        self.assertEqual(r.data["goingCount"], 2)
        self.assertEqual(EventRSVP.objects.count(), 3)

    def test_pending_member_and_anonymous_cannot_rsvp(self):
        pending = make_member("P", login=True, status="pending")
        self.assertEqual(self.rsvp(pending.user, going=True).status_code, 403)
        self.assertEqual(api().post(f"/api/community/events/{self.event.id}/rsvp/", {}, format="json").status_code, 401)

    def test_admin_without_member_row_cannot_rsvp(self):
        self.assertEqual(self.rsvp(self.admin, going=True).status_code, 403)

    def test_unknown_event(self):
        r = api(self.head.user).post("/api/community/events/9999/rsvp/", {}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_event_list_carries_count_and_my_state(self):
        self.rsvp(self.head.user, going=True)
        rows = api(self.head.user).get("/api/community/events/").data
        rows = rows["results"] if isinstance(rows, dict) and "results" in rows else rows
        ev = next(e for e in rows if e["id"] == self.event.id)
        self.assertEqual((ev["going_count"], ev["i_am_going"]), (1, True))
        mine_not = api(self.other_head.user).get("/api/community/events/").data
        mine_not = mine_not["results"] if isinstance(mine_not, dict) and "results" in mine_not else mine_not
        self.assertFalse(next(e for e in mine_not if e["id"] == self.event.id)["i_am_going"])

    def test_deleting_the_event_removes_rsvps(self):
        self.rsvp(self.head.user, going=True)
        self.event.delete()
        self.assertEqual(EventRSVP.objects.count(), 0)


class HomeSummary(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.family, self.head = make_family_with_head("Sachin")
        self.head.native_place = "Gadha"
        self.head.save()

    def get(self, user=None):
        return api(user or self.head.user).get("/api/home/summary/")

    def test_who_am_i_and_village(self):
        d = self.get().data
        self.assertEqual(d["me"]["name"], "Sachin")
        self.assertEqual(d["me"]["role"], "familyHead")
        self.assertEqual(d["me"]["village"], "Gadha")
        self.assertTrue(d["me"]["familyCode"].startswith("F_"))

    def test_village_falls_back_to_city_then_empty(self):
        self.head.native_place = None
        self.head.city = "Idar"
        self.head.save()
        self.assertEqual(self.get().data["me"]["village"], "Idar")
        self.head.city = None
        self.head.save()
        self.assertEqual(self.get().data["me"]["village"], "")

    def test_next_event_is_the_soonest_upcoming_with_my_rsvp(self):
        make_event(self.admin, "Later", days=30)
        soon = make_event(self.admin, "Soon", days=3)
        make_event(self.admin, "Past", days=-5)
        api(self.head.user).post(f"/api/community/events/{soon.id}/rsvp/", {"going": True}, format="json")
        d = self.get().data
        self.assertEqual(d["nextEvent"]["title"], "Soon")
        self.assertEqual(d["nextEvent"]["location"], "Samaj Wadi, Idar")
        self.assertEqual(d["nextEvent"]["time"], "09:00")
        self.assertEqual((d["nextEvent"]["iAmGoing"], d["nextEvent"]["goingCount"]), (True, 1))
        self.assertEqual([e["title"] for e in d["events"]], ["Soon", "Later"])
        self.assertEqual(d["stats"]["upcomingEvents"], 2)

    def test_no_events(self):
        d = self.get().data
        self.assertIsNone(d["nextEvent"])
        self.assertEqual(d["events"], [])

    def test_notices_have_category_ads_have_place_and_price(self):
        Notice.objects.create(title="AGM", description="all heads", category="important", created_by=self.admin, location="Vijapur")
        Notice.objects.create(title="Forms", description="x", created_by=self.admin)
        Advertisement.objects.create(title="Furniture", description="x", price=12000, location="Vijapur", created_by=self.admin)
        d = self.get().data
        cats = {n["title"]: n["category"] for n in d["notices"]}
        self.assertEqual(cats, {"AGM": "important", "Forms": "general"})
        self.assertEqual(d["ads"][0]["price"], "12000.00")
        self.assertEqual(d["ads"][0]["location"], "Vijapur")
        self.assertEqual(d["stats"]["newNotices"], 2)

    def test_counters_and_unread_notifications(self):
        make_member("Another", login=True)
        make_member("Pending", login=True, status="pending")
        Notification.objects.create(user=self.head.user, title="t", message="m", type="approve")
        Notification.objects.create(user=self.head.user, title="t", message="m", type="approve", is_read=True)
        d = self.get().data
        self.assertEqual(d["stats"]["members"], 2)          # only approved people
        self.assertEqual(d["unreadNotifications"], 1)

    def test_blocked_for_pending_and_anonymous_but_admin_works(self):
        pending = make_member("P", login=True, status="pending")
        self.assertEqual(self.get(pending.user).status_code, 403)
        self.assertEqual(api().get("/api/home/summary/").status_code, 401)
        r = self.get(self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["me"]["role"], "admin")
