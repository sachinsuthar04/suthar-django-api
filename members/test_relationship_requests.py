from django.test import TestCase

from members.models import Member, MemberStatus, RelationshipRequest
from members.testing import F, M, api, make_family_with_head, make_member
from notifications.models import Notification


class RelationshipRequests(TestCase):
    def setUp(self):
        self.fa, self.dad = make_family_with_head("Dad")
        self.son = make_member("Son", M, family=self.fa, login=True)
        self.fb, self.other = make_family_with_head("Other")
        self.mum = make_member("Mum", F, login=True)

    def send(self, sender, receiver, relation):
        return api(sender.user).post("/api/members/relationship-requests/",
                                     {"receiver_id": receiver.id, "proposed_relation": relation}, format="json")

    def respond(self, member, req_id, action):
        return api(member.user).post(f"/api/members/relationship-requests/{req_id}/respond/", {"action": action}, format="json")

    def test_father_request_accept_links_sender_to_receiver(self):
        loner = make_member("Loner", M, login=True)
        r = self.send(loner, self.dad, "father")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Notification.objects.filter(user=self.dad.user, type="family_request").exists())
        req = RelationshipRequest.objects.get()
        # receiver sees it in their inbox
        inbox = api(self.dad.user).get("/api/members/relationship-requests/").data["requests"]
        self.assertEqual([i["id"] for i in inbox], [req.id])
        self.assertEqual(self.respond(self.dad, req.id, "accept").status_code, 200)
        loner.refresh_from_db()
        self.assertEqual(loner.father_id, self.dad.id)
        self.assertTrue(Notification.objects.filter(user=loner.user, type="family_request_accepted").exists())

    def test_mother_request(self):
        self.send(self.son, self.mum, "mother")
        self.respond(self.mum, RelationshipRequest.objects.get().id, "accept")
        self.son.refresh_from_db()
        self.assertEqual(self.son.mother_id, self.mum.id)

    def test_child_request_sets_parent_by_sender_gender(self):
        self.send(self.mum, self.son, "son")           # mum says: you are my son
        self.respond(self.son, RelationshipRequest.objects.get().id, "accept")
        self.son.refresh_from_db()
        self.assertEqual(self.son.mother_id, self.mum.id)

    def test_cross_family_marriage_links_both_sides(self):
        self.send(self.son, self.mum, "spouse")
        self.respond(self.mum, RelationshipRequest.objects.get().id, "accept")
        self.son.refresh_from_db(); self.mum.refresh_from_db()
        self.assertEqual((self.son.spouse_id, self.mum.spouse_id), (self.mum.id, self.son.id))
        # and the tree now shows her on his side
        nodes = {n["name"]: n for n in api(self.son.user).get("/api/members/tree/").data["tree"]["nodes"]}
        self.assertEqual(nodes["Mum"]["relation_key"], "wife")

    def test_brother_request_copies_known_parents(self):
        kid_a = make_member("A", M, login=True, father=self.dad)
        kid_b = make_member("B", M, login=True)
        self.send(kid_b, kid_a, "brother")
        self.respond(kid_a, RelationshipRequest.objects.get().id, "accept")
        kid_b.refresh_from_db()
        self.assertEqual(kid_b.father_id, self.dad.id)

    def test_circular_link_is_rejected(self):
        # Dad claims his own son is his father
        self.son.father = self.dad
        self.son.save()
        self.send(self.dad, self.son, "father")
        r = self.respond(self.son, RelationshipRequest.objects.get().id, "accept")
        self.assertEqual(r.status_code, 400)
        self.dad.refresh_from_db()
        self.assertIsNone(self.dad.father_id)
        self.assertEqual(RelationshipRequest.objects.get().status, "pending")

    def test_unsupported_relation_must_go_to_admin(self):
        self.send(self.son, self.mum, "uncle")
        r = self.respond(self.mum, RelationshipRequest.objects.get().id, "accept")
        self.assertEqual(r.status_code, 400)

    def test_reject_changes_nothing(self):
        self.send(self.son, self.mum, "mother")
        self.respond(self.mum, RelationshipRequest.objects.get().id, "reject")
        self.son.refresh_from_db()
        self.assertIsNone(self.son.mother_id)
        self.assertEqual(RelationshipRequest.objects.get().status, "rejected")

    def test_cannot_process_twice(self):
        self.send(self.son, self.mum, "mother")
        rid = RelationshipRequest.objects.get().id
        self.respond(self.mum, rid, "reject")
        self.assertEqual(self.respond(self.mum, rid, "accept").status_code, 400)

    def test_only_receiver_may_respond(self):
        self.send(self.son, self.mum, "mother")
        rid = RelationshipRequest.objects.get().id
        self.assertEqual(self.respond(self.dad, rid, "accept").status_code, 404)
        self.assertEqual(self.respond(self.son, rid, "accept").status_code, 404)

    def test_validation(self):
        self.assertEqual(self.send(self.son, self.son, "father").status_code, 400)
        self.assertEqual(self.send(self.son, self.mum, "nonsense").status_code, 400)
        self.assertEqual(api(self.son.user).post("/api/members/relationship-requests/", {}, format="json").status_code, 400)
        self.send(self.son, self.mum, "mother")
        self.assertEqual(self.send(self.son, self.mum, "mother").status_code, 400)    # duplicate pending

    def test_other_community_is_forbidden(self):
        patel = make_member("Patel", M, login=True, community=2)
        self.assertEqual(self.send(self.son, patel, "spouse").status_code, 403)

    def test_pending_member_cannot_send(self):
        pending = make_member("Pend", M, login=True, status=MemberStatus.PENDING)
        self.assertEqual(self.send(pending, self.mum, "mother").status_code, 403)
