"""One head per family and what the head may / may not do."""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from members.models import (
    Family, FamilyHeadRequest, Member, MemberRole, MemberStatus, ProfileChangeRequest,
)
from members.testing import F, M, api, make_admin, make_family_with_head, make_member, make_user, next_phone
from notifications.models import Notification


def add_payload(name="Kid", mobile=None, relation="son", **extra):
    body = {"name": name, "mobile": mobile or next_phone(), "country_code": "+91",
            "relation": relation, "gender": "male", "date_of_birth": "2015-01-01"}
    body.update(extra)
    return body


class OneHeadPerFamily(TestCase):
    def test_database_rejects_a_second_head_in_the_same_family(self):
        family, head = make_family_with_head()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_member("Second", family=family, role=MemberRole.FAMILY_HEAD)

    def test_two_different_families_each_have_their_own_head(self):
        make_family_with_head("A")
        make_family_with_head("B")
        self.assertEqual(Member.objects.filter(role="familyHead").count(), 2)

    def test_family_head_login_unique(self):
        family, head = make_family_with_head()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Family.objects.create(head=head.user)

    def test_deleting_the_head_login_does_not_delete_the_family(self):
        family, head = make_family_with_head()
        child = make_member("Child", family=family)
        head.user.delete()
        family.refresh_from_db()
        self.assertIsNone(family.head)
        self.assertTrue(Member.objects.filter(id=child.id).exists())

    def test_make_family_head_demotes_old_head(self):
        family, head = make_family_with_head()
        son = make_member("Son", login=True, family=family)
        son.make_family_head()
        head.refresh_from_db()
        son.refresh_from_db()
        family.refresh_from_db()
        self.assertEqual((head.role, son.role), ("member", "familyHead"))
        self.assertEqual(family.head, son.user)
        self.assertEqual(Member.objects.filter(family=family, role="familyHead").count(), 1)


class HeadAddsMembers(TestCase):
    def setUp(self):
        self.family, self.head = make_family_with_head()
        self.client = api(self.head.user)

    def test_added_member_is_pending_and_in_head_family_and_community(self):
        r = self.client.post("/api/members/add/", add_payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        m = Member.objects.get(id=r.data["member"]["id"])
        self.assertEqual((m.status, m.family_id, m.community), (MemberStatus.PENDING, self.family.id, 1))

    @override_settings(HEAD_ADDED_MEMBERS_AUTO_APPROVE=True)
    def test_auto_approve_setting(self):
        r = self.client.post("/api/members/add/", add_payload(), format="json")
        self.assertEqual(Member.objects.get(id=r.data["member"]["id"]).status, MemberStatus.ACTIVE)

    def test_head_cannot_create_another_head(self):
        r = self.client.post("/api/members/add/", add_payload(role="familyHead"), format="json")
        self.assertIn(r.status_code, (201, 400))
        self.assertEqual(Member.objects.filter(family=self.family, role="familyHead").count(), 1)

    def test_son_is_linked_to_head_as_father(self):
        r = self.client.post("/api/members/add/", add_payload(relation="son"), format="json")
        son = Member.objects.get(id=r.data["member"]["id"])
        self.assertEqual(son.father_id, self.head.id)

    def test_wife_is_linked_as_spouse_both_ways(self):
        r = self.client.post("/api/members/add/", add_payload("Wife", relation="spouse", gender="female"), format="json")
        wife = Member.objects.get(id=r.data["member"]["id"])
        self.head.refresh_from_db()
        self.assertEqual((self.head.spouse_id, wife.spouse_id), (wife.id, self.head.id))

    def test_father_is_linked_as_parent_of_head(self):
        r = self.client.post("/api/members/add/", add_payload("Dad", relation="father"), format="json")
        self.head.refresh_from_db()
        self.assertEqual(self.head.father_id, r.data["member"]["id"])

    def test_brother_without_known_parents_still_belongs_to_household(self):
        r = self.client.post("/api/members/add/", add_payload("Bro", relation="brother"), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Member.objects.get(id=r.data["member"]["id"]).family_id, self.family.id)

    def test_mobile_registered_in_another_family_is_conflict(self):
        other_family, other_head = make_family_with_head()
        taken = make_member("Taken", family=other_family, mobile="9333333333")
        r = self.client.post("/api/members/add/", add_payload(mobile="9333333333"), format="json")
        self.assertEqual(r.status_code, 409)

    def test_duplicate_mobile_in_same_family_is_conflict(self):
        self.client.post("/api/members/add/", add_payload(mobile="9444444444"), format="json")
        r = self.client.post("/api/members/add/", add_payload(mobile="9444444444"), format="json")
        self.assertEqual(r.status_code, 409)

    def test_adult_requires_mobile(self):
        body = add_payload(relation="brother")
        body.pop("mobile")
        self.assertEqual(self.client.post("/api/members/add/", body, format="json").status_code, 400)

    def test_cannot_make_self_spouse(self):
        r = self.client.post("/api/members/add/", add_payload(spouse_id=self.head.id), format="json")
        self.assertEqual(r.status_code, 400)

    def test_plain_member_cannot_add(self):
        member = make_member("Plain", login=True, family=self.family)
        self.assertEqual(api(member.user).post("/api/members/add/", add_payload(), format="json").status_code, 403)

    def test_pending_head_cannot_add(self):
        family, head = make_family_with_head()
        head.status = MemberStatus.PENDING
        head.save()
        self.assertEqual(api(head.user).post("/api/members/add/", add_payload(), format="json").status_code, 403)

    def test_admin_is_not_implicitly_a_head(self):
        self.assertEqual(api(make_admin()).post("/api/members/add/", add_payload(), format="json").status_code, 403)

    def test_addition_is_audited(self):
        from members.models import AuditLog
        self.client.post("/api/members/add/", add_payload(), format="json")
        self.assertTrue(AuditLog.objects.filter(action="member_added_by_head").exists())


class HeadEditsAndRemoves(TestCase):
    def setUp(self):
        self.family, self.head = make_family_with_head()
        self.client = api(self.head.user)
        self.active = make_member("Active Son", family=self.family, login=True, date_of_birth=date(2000, 1, 1), relation="son")
        self.pending = make_member("Pending Kid", family=self.family, status=MemberStatus.PENDING,
                                   date_of_birth=date(2015, 1, 1), relation="son", mobile="9555555555")

    def put(self, member, **changes):
        body = {"name": member.name, "role": member.role, "relation": "son", "gender": "male",
                "date_of_birth": str(member.date_of_birth), "mobile": member.mobile}
        body.update(changes)
        return self.client.put(f"/api/members/update/{member.id}/", body, format="json")

    def test_non_key_edit_applies_immediately(self):
        r = self.put(self.active, city="Surat", occupation="Carpenter")
        self.assertEqual(r.status_code, 200, r.data)
        self.active.refresh_from_db()
        self.assertEqual((self.active.city, self.active.occupation), ("Surat", "Carpenter"))
        self.assertEqual(r.data["pending_review"], [])

    def test_key_edit_of_approved_member_is_queued(self):
        r = self.put(self.active, name="Changed By Head")
        self.assertEqual(r.data["pending_review"], ["name"])
        self.active.refresh_from_db()
        self.assertEqual(self.active.name, "Active Son")
        self.assertEqual(ProfileChangeRequest.objects.get().changes["name"]["new"], "Changed By Head")

    def test_key_edit_of_pending_member_applies_directly(self):
        r = self.put(self.pending, name="Corrected")
        self.assertEqual(r.data["pending_review"], [])
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.name, "Corrected")

    def test_head_cannot_change_role_via_update(self):
        r = self.put(self.active, role="familyHead")
        self.assertEqual(r.status_code, 400)
        self.active.refresh_from_db()
        self.assertEqual(self.active.role, "member")

    def test_update_without_spouse_field_keeps_spouse(self):
        wife = make_member("Wife", F, family=self.family)
        self.active.spouse = wife
        self.active.save()
        wife.spouse = self.active
        wife.save()
        self.put(self.active, city="X")
        self.active.refresh_from_db()
        self.assertEqual(self.active.spouse_id, wife.id)

    def test_mark_member_deceased(self):
        r = self.put(self.active, is_alive=False, date_of_death="2026-01-01")
        self.assertEqual(r.status_code, 200, r.data)
        self.active.refresh_from_db()
        self.assertFalse(self.active.is_alive)
        self.assertEqual(str(self.active.date_of_death), "2026-01-01")

    def test_cannot_edit_member_of_another_family(self):
        other_family, _ = make_family_with_head()
        stranger = make_member("Stranger", family=other_family, date_of_birth=date(1990, 1, 1))
        r = self.client.put(f"/api/members/update/{stranger.id}/", {"name": "x"}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_remove_keeps_person_and_tree_links(self):
        grandkid = make_member("Grandkid", family=self.family, father=self.active)
        self.assertEqual(self.client.delete(f"/api/members/delete/{self.active.id}/").status_code, 200)
        self.active.refresh_from_db()
        self.assertIsNone(self.active.family_id)                 # left the household ...
        self.assertTrue(Member.objects.filter(id=self.active.id).exists())  # ... but is not deleted
        grandkid.refresh_from_db()
        self.assertEqual(grandkid.father_id, self.active.id)     # tree link intact
        ids = {m["id"] for m in self.client.get("/api/members/my-family/").data["familyMembers"]}
        self.assertNotIn(self.active.id, ids)

    def test_head_cannot_remove_himself(self):
        self.assertEqual(self.client.delete(f"/api/members/delete/{self.head.id}/").status_code, 400)
        self.head.refresh_from_db()
        self.assertEqual(self.head.family_id, self.family.id)

    def test_cannot_remove_other_family_member(self):
        other_family, _ = make_family_with_head()
        stranger = make_member("Stranger", family=other_family)
        self.assertEqual(self.client.delete(f"/api/members/delete/{stranger.id}/").status_code, 404)

    def test_plain_member_cannot_edit_or_remove(self):
        c = api(self.active.user)
        self.assertEqual(c.delete(f"/api/members/delete/{self.pending.id}/").status_code, 403)
        self.assertEqual(c.put(f"/api/members/update/{self.pending.id}/", {}, format="json").status_code, 403)


class TransferHeadship(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.family, self.head = make_family_with_head()
        self.son = make_member("Son", login=True, family=self.family, date_of_birth=date(1995, 1, 1))
        self.client = api(self.head.user)

    def request_transfer(self, target=None, who=None):
        return (who or self.client).post("/api/members/head-requests/",
                                         {"kind": "transfer", "member_id": (target or self.son).id}, format="json")

    def test_full_transfer_flow(self):
        r = self.request_transfer()
        self.assertEqual(r.status_code, 201, r.data)
        req_id = r.data["request"]["id"]
        # nothing changes until admin accepts
        self.head.refresh_from_db()
        self.assertEqual(self.head.role, "familyHead")

        r = api(self.admin).post(f"/api/members/head-requests/{req_id}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.head.refresh_from_db()
        self.son.refresh_from_db()
        self.family.refresh_from_db()
        self.assertEqual((self.head.role, self.son.role), ("member", "familyHead"))
        self.assertEqual(self.family.head, self.son.user)
        self.assertEqual(Member.objects.filter(family=self.family, role="familyHead").count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.son.user, type="head_request").exists())
        # new head can add, old head cannot any more
        self.assertEqual(api(self.son.user).post("/api/members/add/", add_payload(), format="json").status_code, 201)
        self.assertEqual(api(self.head.user).post("/api/members/add/", add_payload(), format="json").status_code, 403)

    def test_only_head_can_request_transfer(self):
        self.assertEqual(self.request_transfer(who=api(self.son.user), target=self.head).status_code, 403)

    def test_target_must_be_in_same_family(self):
        other_family, _ = make_family_with_head()
        stranger = make_member("S", login=True, family=other_family, date_of_birth=date(1990, 1, 1))
        self.assertEqual(self.request_transfer(target=stranger).status_code, 404)

    def test_target_must_have_login_be_approved_and_adult(self):
        no_login = make_member("NoLogin", family=self.family, date_of_birth=date(1990, 1, 1))
        self.assertEqual(self.request_transfer(target=no_login).status_code, 400)
        pending = make_member("Pend", login=True, family=self.family, status=MemberStatus.PENDING, date_of_birth=date(1990, 1, 1))
        self.assertEqual(self.request_transfer(target=pending).status_code, 400)
        kid = make_member("Kid", login=True, family=self.family, date_of_birth=date.today())
        self.assertEqual(self.request_transfer(target=kid).status_code, 400)

    def test_cannot_transfer_to_self(self):
        self.assertEqual(self.request_transfer(target=self.head).status_code, 400)

    def test_second_pending_transfer_is_conflict(self):
        self.request_transfer()
        other = make_member("Other", login=True, family=self.family, date_of_birth=date(1990, 1, 1))
        self.assertEqual(self.request_transfer(target=other).status_code, 409)

    def test_admin_can_reject_and_nothing_changes(self):
        req_id = self.request_transfer().data["request"]["id"]
        api(self.admin).post(f"/api/members/head-requests/{req_id}/respond/", {"action": "reject", "reason": "no"}, format="json")
        self.head.refresh_from_db()
        self.assertEqual(self.head.role, "familyHead")
        self.assertEqual(FamilyHeadRequest.objects.get().status, "rejected")

    def test_non_admin_cannot_respond_and_cannot_respond_twice(self):
        req_id = self.request_transfer().data["request"]["id"]
        self.assertEqual(api(self.head.user).post(f"/api/members/head-requests/{req_id}/respond/", {"action": "accept"}, format="json").status_code, 403)
        admin = api(self.admin)
        admin.post(f"/api/members/head-requests/{req_id}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(admin.post(f"/api/members/head-requests/{req_id}/respond/", {"action": "accept"}, format="json").status_code, 400)

    def test_listing_shows_admin_all_pending_and_head_own_family(self):
        self.request_transfer()
        self.assertEqual(len(api(self.admin).get("/api/members/head-requests/").data["requests"]), 1)
        self.assertEqual(len(self.client.get("/api/members/head-requests/").data["requests"]), 1)
        other_family, other_head = make_family_with_head()
        self.assertEqual(len(api(other_head.user).get("/api/members/head-requests/").data["requests"]), 0)


class NewHousehold(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.family, self.head = make_family_with_head()
        self.son = make_member("Married Son", login=True, family=self.family, date_of_birth=date(1990, 1, 1),
                               father=self.head)

    def test_member_requests_separate_household_admin_approves(self):
        r = api(self.son.user).post("/api/members/head-requests/", {"kind": "new_household"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = api(self.admin).post(f"/api/members/head-requests/{r.data['request']['id']}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.son.refresh_from_db()
        self.assertEqual(self.son.role, "familyHead")
        self.assertNotEqual(self.son.family_id, self.family.id)
        self.assertEqual(self.son.family.head, self.son.user)
        # still the father's child in the tree
        self.assertEqual(self.son.father_id, self.head.id)
        # old family keeps its single head
        self.assertEqual(Member.objects.filter(family=self.family, role="familyHead").count(), 1)

    def test_existing_head_cannot_request_new_household(self):
        r = api(self.head.user).post("/api/members/head-requests/", {"kind": "new_household"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_duplicate_request_is_conflict(self):
        c = api(self.son.user)
        c.post("/api/members/head-requests/", {"kind": "new_household"}, format="json")
        self.assertEqual(c.post("/api/members/head-requests/", {"kind": "new_household"}, format="json").status_code, 409)

    def test_member_without_login_cannot_be_head(self):
        from members.services import households
        ghost = make_member("Ghost", family=self.family)
        with self.assertRaises(households.HeadRequestError):
            households.validate_new_household(ghost)

    def test_invalid_kind(self):
        self.assertEqual(api(self.son.user).post("/api/members/head-requests/", {"kind": "x"}, format="json").status_code, 400)


class HealerNeverInventsBadParents(TestCase):
    """Regression for real data: spouse wrongly stored as male made the head
    his own children's mother."""

    def test_same_gender_couple_does_not_create_self_as_mother(self):
        from members.utils import heal_family_relations
        family, head = make_family_with_head("Sachin")
        head.gender = M
        head.save()
        wife = make_member("Juee", M, family=family)         # wrong gender in the data
        head.spouse = wife; head.save()
        wife.spouse = head; wife.save()
        kid = make_member("Kid", M, family=family, father=head)
        heal_family_relations(family)
        kid.refresh_from_db()
        self.assertNotEqual(kid.mother_id, head.id)
        self.assertNotEqual(kid.father_id, kid.mother_id)


class CheckFamilyDataCommand(TestCase):
    def test_reports_problems_without_changing_anything(self):
        from io import StringIO
        from django.core.management import call_command
        family, head = make_family_with_head("Sachin")
        kid = make_member("Kid", M, family=family, father=head, mother=head)
        wife = make_member("Juee", M, family=family)
        head.spouse = wife; head.save()
        out = StringIO()
        call_command("check_family_data", stdout=out)
        text = out.getvalue()
        self.assertIn("father and mother are the same person", text)
        self.assertIn("spouse #", text)
        kid.refresh_from_db()
        self.assertEqual(kid.mother_id, head.id)      # untouched

    def test_clean_data_reports_nothing(self):
        from io import StringIO
        from django.core.management import call_command
        family, head = make_family_with_head("Ok")
        out = StringIO()
        call_command("check_family_data", stdout=out)
        self.assertIn("No problems found", out.getvalue())
