"""Approval flow: registration -> pending -> admin decision, key-field review."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from members.models import (
    AuditLog, Family, FamilyHeadRequest, Member, MemberRole, MemberStatus,
    ProfileChangeRequest, ReviewStatus,
)
from members.testing import api, make_admin, make_family_with_head, make_member, make_user, next_phone
from notifications.models import Notification
from profiles.models import PersonalDetail, UserProfile


def profile_payload(phone, name="Ravi Suthar", role="member", **personal):
    body = {
        "selectedRole": role,
        "personal": {
            "fullName": name, "gender": "male", "dob": "1990-05-05", "phone": phone,
            "country_code": "+91", "nativePlace": "Palanpur", "community": 1,
            **personal,
        },
    }
    return body


class RegistrationIsServerControlled(TestCase):
    def test_new_user_becomes_pending_member_even_if_client_sends_active_and_head(self):
        user = make_user()
        body = profile_payload(user.phone, role="familyHead", status="active")
        body["personal"]["status"] = "active"
        r = api(user).post("/api/profiles/profile/save/", body, format="json")
        self.assertEqual(r.status_code, 200)
        member = Member.objects.get(user=user)
        self.assertEqual(member.status, MemberStatus.PENDING)     # not self-approved
        self.assertEqual(member.role, MemberRole.MEMBER)          # not self-promoted
        self.assertIsNone(member.family_id)
        self.assertTrue(r.data["headRequestPending"])
        self.assertTrue(FamilyHeadRequest.objects.filter(member=member, status="pending").exists())
        self.assertFalse(Family.objects.filter(head=user).exists())
        self.assertEqual(r.data["status"], "pending")

    def test_pending_member_cannot_flip_status_by_resaving_profile(self):
        user = make_user()
        api(user).post("/api/profiles/profile/save/", profile_payload(user.phone), format="json")
        body = profile_payload(user.phone)
        body["personal"]["status"] = "active"
        api(user).post("/api/profiles/profile/save/", body, format="json")
        self.assertEqual(Member.objects.get(user=user).status, MemberStatus.PENDING)
        self.assertEqual(PersonalDetail.objects.get(profile__user=user).status, MemberStatus.PENDING)

    def test_incomplete_profile_is_reported_incomplete_then_pending(self):
        user = make_user()
        api(user).post("/api/profiles/profile/save/", {"personal": {"fullName": "Half", "phone": user.phone}}, format="json")
        self.assertEqual(api(user).get("/api/members/me/status/").data["status"], "incomplete")
        api(user).post("/api/profiles/profile/save/", profile_payload(user.phone, name="Half"), format="json")
        self.assertEqual(api(user).get("/api/members/me/status/").data["status"], "pending")

    def test_user_without_any_member_row_is_incomplete(self):
        r = api(make_user()).get("/api/members/me/status/")
        self.assertEqual(r.data["status"], "incomplete")

    def test_role_never_changes_through_profile_save(self):
        family, head = make_family_with_head()
        member = make_member("Son", login=True, family=family)
        api(member.user).post("/api/profiles/profile/save/",
                              profile_payload(member.mobile, name="Son", role="familyHead"), format="json")
        member.refresh_from_db()
        self.assertEqual(member.role, MemberRole.MEMBER)
        # already belongs to a household: no new-household request is created silently
        self.assertFalse(FamilyHeadRequest.objects.filter(member=member).exists())
        head.refresh_from_db()
        self.assertEqual(head.role, MemberRole.FAMILY_HEAD)

    def test_head_added_member_logging_in_links_instead_of_duplicating(self):
        family, head = make_family_with_head()
        added = make_member("Added", family=family, status=MemberStatus.PENDING, mobile="9111111111")
        user = make_user("9111111111")
        added.user = user
        added.save()
        api(user).post("/api/profiles/profile/save/", profile_payload("9111111111", name="Added"), format="json")
        self.assertEqual(Member.objects.filter(mobile="9111111111").count(), 1)
        added.refresh_from_db()
        self.assertEqual(added.family_id, family.id)
        self.assertEqual(added.status, MemberStatus.PENDING)


class AdminDecision(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user()
        api(self.user).post("/api/profiles/profile/save/", profile_payload(self.user.phone), format="json")
        self.member = Member.objects.get(user=self.user)

    def decide(self, status, reason=None, who=None):
        body = {"status": status}
        if reason:
            body["reason"] = reason
        return api(who or self.admin).post(f"/api/members/accept-reject/{self.member.id}/", body, format="json")

    def test_only_admin_can_decide(self):
        other = make_member("Other", login=True)
        self.assertEqual(self.decide("active", who=other.user).status_code, 403)
        self.assertEqual(self.decide("active", who=self.user).status_code, 403)
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.PENDING)

    def test_approve_activates_notifies_audits_and_syncs_profile(self):
        self.assertEqual(self.decide("active").status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.ACTIVE)
        self.assertEqual(self.member.status_changed_by, self.admin)
        self.assertIsNotNone(self.member.status_changed_at)
        self.assertEqual(PersonalDetail.objects.get(profile__user=self.user).status, "active")
        self.assertTrue(Notification.objects.filter(user=self.user, type="approve").exists())
        self.assertTrue(AuditLog.objects.filter(action="member_active", entity_id=self.member.id).exists())
        self.assertEqual(api(self.user).get("/api/members/me/status/").data["status"], "active")
        self.assertEqual(api(self.user).get("/api/members/my-family/").status_code, 200)

    def test_reject_with_reason_blocks_api_and_is_visible_to_user(self):
        self.decide("active")
        self.assertEqual(self.decide("rejected", reason="Not from our samaj").status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.status_reason, "Not from our samaj")
        status = api(self.user).get("/api/members/me/status/").data
        self.assertEqual((status["status"], status["reason"]), ("rejected", "Not from our samaj"))
        self.assertEqual(api(self.user).get("/api/members/my-family/").status_code, 403)
        note = Notification.objects.get(user=self.user, type="reject")
        self.assertIn("Not from our samaj", note.message)

    def test_reapproval_clears_old_reason(self):
        self.decide("rejected", reason="Missing data")
        self.decide("active")
        self.member.refresh_from_db()
        self.assertIsNone(self.member.status_reason)

    def test_invalid_status_rejected(self):
        self.assertEqual(self.decide("superadmin").status_code, 400)

    def test_approving_member_without_login_does_not_crash(self):
        family, _ = make_family_with_head()
        ghost = make_member("Ghost", family=family, status=MemberStatus.PENDING)
        r = api(self.admin).post(f"/api/members/accept-reject/{ghost.id}/", {"status": "active"}, format="json")
        self.assertEqual(r.status_code, 200)
        ghost.refresh_from_db()
        self.assertEqual(ghost.status, MemberStatus.ACTIVE)

    def test_unknown_member_404(self):
        self.assertEqual(api(self.admin).post("/api/members/accept-reject/99999/", {"status": "active"}, format="json").status_code, 404)

    def test_approving_a_head_candidate_creates_exactly_one_family(self):
        self.member.delete()
        user = make_user()
        api(user).post("/api/profiles/profile/save/", profile_payload(user.phone, role="familyHead"), format="json")
        member = Member.objects.get(user=user)
        r = api(self.admin).post(f"/api/members/accept-reject/{member.id}/", {"status": "active"}, format="json")
        self.assertEqual(r.status_code, 200)
        member.refresh_from_db()
        self.assertEqual(member.role, MemberRole.FAMILY_HEAD)
        self.assertEqual(member.family.head, user)
        self.assertEqual(Member.objects.filter(family=member.family, role="familyHead").count(), 1)
        self.assertEqual(UserProfile.objects.get(user=user).registration_role, "familyHead")
        self.assertEqual(FamilyHeadRequest.objects.get(member=member).status, ReviewStatus.ACCEPTED)
        self.assertEqual(api(user).get("/api/members/me/status/").data["isFamilyHead"], True)

    def test_rejecting_a_head_candidate_rejects_the_head_request_too(self):
        self.member.delete()
        user = make_user()
        api(user).post("/api/profiles/profile/save/", profile_payload(user.phone, role="familyHead"), format="json")
        member = Member.objects.get(user=user)
        api(self.admin).post(f"/api/members/accept-reject/{member.id}/", {"status": "rejected", "reason": "dup"}, format="json")
        self.assertEqual(FamilyHeadRequest.objects.get(member=member).status, ReviewStatus.REJECTED)
        self.assertFalse(Family.objects.filter(head=user).exists())


class KeyFieldReview(TestCase):
    """After approval, name / gender / dob / gotra edits wait for an admin."""

    def setUp(self):
        self.admin = make_admin()
        self.user = make_user()
        api(self.user).post("/api/profiles/profile/save/", profile_payload(self.user.phone), format="json")
        self.member = Member.objects.get(user=self.user)
        api(self.admin).post(f"/api/members/accept-reject/{self.member.id}/", {"status": "active"}, format="json")

    def save(self, **personal):
        return api(self.user).post("/api/profiles/profile/save/", profile_payload(self.user.phone, **personal), format="json")

    def test_pending_member_can_still_edit_everything_directly(self):
        u = make_user()
        api(u).post("/api/profiles/profile/save/", profile_payload(u.phone), format="json")
        api(u).post("/api/profiles/profile/save/", profile_payload(u.phone, name="Fixed Name"), format="json")
        self.assertEqual(Member.objects.get(user=u).name, "Fixed Name")
        self.assertFalse(ProfileChangeRequest.objects.filter(member__user=u).exists())

    def test_name_change_is_queued_old_value_stays_live(self):
        r = self.save(name="New Name")
        self.assertEqual(r.data["pendingReview"], ["name"])
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, "Ravi Suthar")
        self.assertEqual(PersonalDetail.objects.get(profile__user=self.user).full_name, "Ravi Suthar")
        self.assertEqual(self.member.status, MemberStatus.ACTIVE)        # stays active
        self.assertTrue(self.member.profile_completed)
        req = ProfileChangeRequest.objects.get(member=self.member)
        self.assertEqual(req.changes["name"], {"old": "Ravi Suthar", "new": "New Name"})

    def test_non_key_fields_apply_immediately(self):
        r = self.save(currentCity="Surat", email="r@x.com")
        self.assertEqual(r.data["pendingReview"], [])
        self.member.refresh_from_db()
        self.assertEqual((self.member.city, self.member.email), ("Surat", "r@x.com"))

    def test_unchanged_values_create_no_request(self):
        self.save()
        self.assertFalse(ProfileChangeRequest.objects.exists())

    def test_dob_and_gender_are_key_fields(self):
        r = self.save(dob="1991-01-01", gender="female")
        self.assertEqual(r.data["pendingReview"], ["date_of_birth", "gender"])
        self.member.refresh_from_db()
        self.assertEqual(str(self.member.date_of_birth), "1990-05-05")
        self.assertEqual(self.member.gender, "male")

    def test_repeated_edits_merge_into_one_request_keeping_first_old_value(self):
        self.save(name="Second")
        self.save(name="Third")
        req = ProfileChangeRequest.objects.get()
        self.assertEqual(req.changes["name"], {"old": "Ravi Suthar", "new": "Third"})

    def test_admin_accepts_change_applies_it_and_notifies(self):
        self.save(name="Approved Name", dob="1992-02-02")
        req = ProfileChangeRequest.objects.get()
        r = api(self.admin).post(f"/api/members/change-requests/{req.id}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, "Approved Name")
        self.assertEqual(str(self.member.date_of_birth), "1992-02-02")
        personal = PersonalDetail.objects.get(profile__user=self.user)
        self.assertEqual((personal.full_name, str(personal.dob)), ("Approved Name", "1992-02-02"))
        req.refresh_from_db()
        self.assertEqual((req.status, req.reviewed_by), (ReviewStatus.ACCEPTED, self.admin))
        self.assertTrue(Notification.objects.filter(user=self.user, type="profile_change").exists())

    def test_admin_rejects_change_value_unchanged(self):
        self.save(name="Rejected Name")
        req = ProfileChangeRequest.objects.get()
        api(self.admin).post(f"/api/members/change-requests/{req.id}/respond/", {"action": "reject", "reason": "wrong"}, format="json")
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, "Ravi Suthar")
        req.refresh_from_db()
        self.assertEqual((req.status, req.reason), (ReviewStatus.REJECTED, "wrong"))

    def test_processed_request_cannot_be_processed_twice_and_member_cannot_approve(self):
        self.save(name="X")
        req = ProfileChangeRequest.objects.get()
        self.assertEqual(api(self.user).post(f"/api/members/change-requests/{req.id}/respond/", {"action": "accept"}, format="json").status_code, 403)
        api(self.admin).post(f"/api/members/change-requests/{req.id}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(api(self.admin).post(f"/api/members/change-requests/{req.id}/respond/", {"action": "accept"}, format="json").status_code, 400)

    def test_status_endpoint_lists_pending_fields(self):
        self.save(name="Y")
        self.assertEqual(api(self.user).get("/api/members/me/status/").data["pendingChangeFields"], ["name"])

    @override_settings(KEY_FIELD_REVIEW=False)
    def test_review_can_be_switched_off(self):
        self.save(name="Direct")
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, "Direct")


class AdminQueue(TestCase):
    def test_queue_groups_everything_an_admin_must_review(self):
        admin = make_admin()
        make_member("New", login=True, status=MemberStatus.PENDING)
        make_member("Half", login=True, status=MemberStatus.PENDING, profile_completed=False)
        make_member("Rej", login=True, status=MemberStatus.REJECTED, status_reason="no")
        active = make_member("Act", login=True)
        ProfileChangeRequest.objects.create(member=active, changes={"name": {"old": "a", "new": "b"}})
        FamilyHeadRequest.objects.create(member=active, kind="new_household")
        data = api(admin).get("/api/members/admin/queue/").data
        self.assertEqual(data["counts"], {"newRegistrations": 1, "incomplete": 1, "profileChanges": 1,
                                          "headRequests": 1, "rejected": 1})
        self.assertEqual(data["rejected"][0]["reason"], "no")

    def test_queue_is_admin_only(self):
        self.assertEqual(api(make_member("M", login=True).user).get("/api/members/admin/queue/").status_code, 403)


class EndToEndWithOtp(TestCase):
    """OTP stays as-is (master code 123456): full flow through the real endpoints."""

    def test_register_approve_login_flow(self):
        phone = "9876500000"
        client = APIClient()
        r = client.post("/api/auth/verify-otp/", {"phone": phone, "country_code": "+91", "otp": "123456",
                                                  "fcm_token": "tok-1"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["firstTime"])
        self.assertFalse(r.data["profileCompleted"])
        token = r.data["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(client.get("/api/members/me/status/").data["status"], "incomplete")
        self.assertEqual(client.get("/api/members/my-family/").status_code, 403)

        client.post("/api/profiles/profile/save/", profile_payload(phone), format="json")
        self.assertEqual(client.get("/api/members/me/status/").data["status"], "pending")

        member = Member.objects.get(mobile=phone)
        api(make_admin()).post(f"/api/members/accept-reject/{member.id}/", {"status": "active"}, format="json")

        self.assertEqual(client.get("/api/members/me/status/").data["status"], "active")
        self.assertEqual(client.get("/api/members/my-family/").status_code, 200)

        # second login keeps the same account and reports approval
        r = client.post("/api/auth/verify-otp/", {"phone": phone, "country_code": "+91", "otp": "123456"}, format="json")
        self.assertFalse(r.data["firstTime"])
        self.assertEqual(r.data["data"]["personal"]["status"], "active")

    def test_wrong_otp_is_rejected(self):
        r = APIClient().post("/api/auth/verify-otp/", {"phone": "9000000099", "country_code": "+91", "otp": "000000"}, format="json")
        self.assertEqual(r.status_code, 400)


class EditAndResend(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user()
        api(self.user).post("/api/profiles/profile/save/", profile_payload(self.user.phone), format="json")
        self.member = Member.objects.get(user=self.user)
        api(self.admin).post(f"/api/members/accept-reject/{self.member.id}/", {"status": "rejected", "reason": "Add village"}, format="json")

    def test_rejected_member_fixing_profile_goes_back_to_pending_and_queue(self):
        r = api(self.user).post("/api/profiles/profile/save/", profile_payload(self.user.phone, nativePlace="Gadha"), format="json")
        self.assertTrue(r.data["resubmitted"])
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.PENDING)
        self.assertIsNone(self.member.status_reason)
        self.assertEqual(PersonalDetail.objects.get(profile__user=self.user).status, "pending")
        self.assertTrue(AuditLog.objects.filter(action="member_resubmitted", data__previous_reason="Add village").exists())
        queue = api(self.admin).get("/api/members/admin/queue/").data
        self.assertEqual(queue["counts"]["newRegistrations"], 1)
        self.assertEqual(queue["counts"]["rejected"], 0)

    def test_rejected_stays_rejected_if_profile_still_incomplete(self):
        r = api(self.user).post("/api/profiles/profile/save/", {"personal": {"nativePlace": ""}}, format="json")
        self.assertFalse(r.data["profileCompleted"])
        self.assertFalse(r.data["resubmitted"])
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.REJECTED)

    def test_active_member_save_is_not_a_resubmission(self):
        api(self.admin).post(f"/api/members/accept-reject/{self.member.id}/", {"status": "active"}, format="json")
        r = api(self.user).post("/api/profiles/profile/save/", profile_payload(self.user.phone), format="json")
        self.assertFalse(r.data["resubmitted"])
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, MemberStatus.ACTIVE)
