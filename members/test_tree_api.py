"""Ego-centred family tree API: read only, bounded queries, correct per viewer."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from members.models import Member, MemberStatus
from members.testing import F, M, api, make_admin, make_family_with_head, make_member


class BigFamily(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        # paternal grandparents
        cls.G1 = make_member("G1", M)
        cls.G2 = make_member("G2", F, spouse=cls.G1)
        cls.G1.spouse = cls.G2; cls.G1.save()
        # maternal grandparents
        cls.MG1 = make_member("MG1", M)
        cls.MG2 = make_member("MG2", F, spouse=cls.MG1)
        cls.MG1.spouse = cls.MG2; cls.MG1.save()
        # the household (father is head)
        cls.family, cls.F = make_family_with_head("Father")
        cls.F.father, cls.F.mother = cls.G1, cls.G2
        cls.F.save()
        cls.Mo = make_member("Mother", F, family=cls.family, mother=cls.MG2, father=cls.MG1, login=True)
        cls.F.spouse = cls.Mo; cls.F.save()
        cls.Mo.spouse = cls.F; cls.Mo.save()
        cls.E = make_member("Ego", M, family=cls.family, father=cls.F, mother=cls.Mo, login=True)
        cls.Bro = make_member("Brother", M, family=cls.family, father=cls.F, mother=cls.Mo)
        cls.Sis = make_member("Sister", F, family=cls.family, father=cls.F, mother=cls.Mo)
        # relatives
        cls.K = make_member("Kaka", M, father=cls.G1, mother=cls.G2)
        cls.Bua = make_member("Bua", F, father=cls.G1, mother=cls.G2)
        cls.Cousin = make_member("Cousin", M, father=cls.K)
        cls.Mama = make_member("Mama", M, father=cls.MG1, mother=cls.MG2)
        cls.Masi = make_member("Masi", F, father=cls.MG1, mother=cls.MG2)
        # ego's wife and her family
        cls.WF = make_member("WifeFather", M)
        cls.WM = make_member("WifeMother", F, spouse=cls.WF)
        cls.WF.spouse = cls.WM; cls.WF.save()
        cls.W = make_member("Wife", F, family=cls.family, father=cls.WF, mother=cls.WM, spouse=cls.E)
        cls.E.spouse = cls.W; cls.E.save()
        cls.WB = make_member("WifeBrother", M, father=cls.WF, mother=cls.WM)
        cls.WS = make_member("WifeSister", F, father=cls.WF, mother=cls.WM)
        # ego's children
        cls.S = make_member("Son", M, family=cls.family, father=cls.E, mother=cls.W)
        cls.D = make_member("Daughter", F, family=cls.family, father=cls.E, mother=cls.W)
        cls.GS = make_member("Grandson", M, father=cls.S)
        # logins we need
        cls.S.user = make_member("tmp", login=True).user; cls.S.save()
        # someone in the same household with NO links at all
        cls.Floating = make_member("Floating", M, family=cls.family)

    def tree(self, user, url="/api/members/tree/"):
        r = api(user).get(url)
        self.assertEqual(r.status_code, 200, r.data)
        nodes = {n["name"]: n for n in r.data["tree"]["nodes"]}
        return r, nodes

    def rel(self, nodes, name):
        return nodes[name]["relation_key"]

    # ------------------------------------------------------------------
    def test_son_logs_in_sees_father_mother_siblings_uncles_aunts_and_own_family(self):
        r, n = self.tree(self.E.user)
        self.assertEqual(r.data["ego_id"], self.E.id)
        expected = {
            "Ego": "self", "Father": "father", "Mother": "mother", "Brother": "brother",
            "Sister": "sister", "G1": "grandfather", "G2": "grandmother",
            "MG1": "grandfather", "MG2": "grandmother",
            "Kaka": "kaka", "Bua": "bua", "Cousin": "cousin_brother",
            "Mama": "mama", "Masi": "masi",
            "Wife": "wife", "WifeFather": "father_in_law", "WifeMother": "mother_in_law",
            "WifeBrother": "saala", "WifeSister": "saali",
            "Son": "son", "Daughter": "daughter", "Grandson": "grandson",
        }
        for name, key in expected.items():
            self.assertIn(name, n, f"{name} missing from tree")
            self.assertEqual(self.rel(n, name), key, name)

    def test_father_logs_in_sees_parents_wife_children_grandchildren_and_brothers_not_wifes_parents(self):
        r, n = self.tree(self.F.user)
        expected = {"Father": "self", "G1": "father", "G2": "mother", "Mother": "wife", "Kaka": "brother",
                    "Bua": "sister", "Ego": "son", "Brother": "son", "Sister": "daughter",
                    "Wife": "daughter_in_law", "Son": "grandson", "Daughter": "granddaughter",
                    "Cousin": "nephew", "MG1": "father_in_law", "MG2": "mother_in_law",
                    "Mama": "saala", "Masi": "saali"}
        for name, key in expected.items():
            self.assertIn(name, n, name)
            self.assertEqual(self.rel(n, name), key, name)
        self.assertNotIn("WifeFather", n)    # his daughter-in-law's parents: not his lineage view

    def test_wife_logs_in_sees_husbands_side_as_in_laws(self):
        self.W.user = make_member("tmpw", login=True).user
        self.W.save()
        r, n = self.tree(self.W.user)
        self.assertEqual(self.rel(n, "Ego"), "husband")
        self.assertEqual(self.rel(n, "Father"), "father_in_law")
        self.assertEqual(self.rel(n, "Mother"), "mother_in_law")
        self.assertEqual(self.rel(n, "Brother"), "devar")
        self.assertEqual(self.rel(n, "Sister"), "nanand")
        self.assertEqual(self.rel(n, "WifeFather"), "father")
        self.assertEqual(self.rel(n, "WifeBrother"), "brother")

    def test_tree_as_another_person_recentres(self):
        r, n = self.tree(self.E.user, f"/api/members/tree/{self.Bro.id}/")
        self.assertEqual(r.data["ego_id"], self.Bro.id)
        self.assertEqual(self.rel(n, "Brother"), "self")
        self.assertEqual(self.rel(n, "Ego"), "brother")

    def test_household_member_with_no_links_is_still_shown(self):
        r, n = self.tree(self.E.user)
        self.assertIn("Floating", n)
        edges = r.data["tree"]["edges"]
        fid = self.Floating.id
        self.assertFalse([e for e in edges if fid in (e["source"], e["target"])])

    def test_edges_are_complete_unique_and_typed(self):
        r, n = self.tree(self.E.user)
        edges = r.data["tree"]["edges"]
        keyed = {(e["source"], e["target"], e["type"]) for e in edges}
        self.assertEqual(len(keyed), len(edges))
        self.assertIn((self.F.id, self.E.id, "father"), keyed)
        self.assertIn((self.Mo.id, self.E.id, "mother"), keyed)
        self.assertIn((self.G1.id, self.F.id, "father"), keyed)
        spouse_edges = [e for e in edges if e["type"] == "spouse"]
        pairs = {frozenset((e["source"], e["target"])) for e in spouse_edges}
        self.assertEqual(len(pairs), len(spouse_edges))                    # each marriage once
        self.assertIn(frozenset((self.E.id, self.W.id)), pairs)
        node_ids = {x["id"] for x in n.values()}
        self.assertTrue(all(e["source"] in node_ids and e["target"] in node_ids for e in edges))

    def test_up_down_and_inlaw_parameters(self):
        _, n = self.tree(self.E.user, "/api/members/tree/?up=1")
        self.assertIn("Father", n)
        self.assertNotIn("G1", n)
        _, n = self.tree(self.E.user, "/api/members/tree/?down=0&collateral=0&inlaws=false")
        self.assertNotIn("Grandson", n)    # not in the household, beyond down=0
        self.assertNotIn("WifeFather", n)
        self.assertIn("Wife", n)           # spouse is always there
        self.assertIn("Son", n)            # household members are always shown
        _, n = self.tree(self.E.user, "/api/members/tree/?down=abc")   # bad value -> default
        self.assertIn("Son", n)

    # ------------------------------------------------------------------
    def test_get_never_writes_to_the_database(self):
        # a head with a text-only "spouse" that the old code would 'heal' on GET
        family, head = make_family_with_head("Lonely")
        unlinked = make_member("TextWife", F, family=family, relation="spouse")
        snapshot = lambda: sorted(Member.objects.values_list(
            "id", "father_id", "mother_id", "spouse_id", "family_id", "status", "role", "name"))
        before = snapshot()
        api(head.user).get("/api/members/tree/")
        api(self.E.user).get("/api/members/tree/")
        api(self.admin).get(f"/api/members/tree/{self.E.id}/")
        self.assertEqual(snapshot(), before)
        head.refresh_from_db()
        self.assertIsNone(head.spouse_id)

    def test_query_count_does_not_grow_with_family_size(self):
        with CaptureQueriesContext(connection) as small:
            api(self.E.user).get("/api/members/tree/")
        # add 25 more people around the ego
        for i in range(25):
            kid = make_member(f"Extra{i}", M, family=self.family, father=self.E, mother=self.W)
            make_member(f"ExtraGrand{i}", F, father=kid)
        with CaptureQueriesContext(connection) as big:
            r = api(self.E.user).get("/api/members/tree/")
        self.assertGreater(len(r.data["tree"]["nodes"]), 50)
        self.assertLessEqual(len(big) - len(small), 4, (len(small), len(big)))
        self.assertLess(len(big), 60)

    # ------------------------------------------------------------------
    def test_access_rules(self):
        other_family, other_head = make_family_with_head("Outsider")
        # same community, other family: allowed (it is one samaj's lineage)
        self.assertEqual(api(other_head.user).get(f"/api/members/tree/{self.E.id}/").status_code, 200)
        # another community: forbidden
        patel_family, patel_head = make_family_with_head("Patel", community=2)
        self.assertEqual(api(patel_head.user).get(f"/api/members/tree/{self.E.id}/").status_code, 403)
        # admin: any, but needs an explicit person (no own member)
        self.assertEqual(api(self.admin).get(f"/api/members/tree/{self.E.id}/").status_code, 200)
        self.assertEqual(api(self.admin).get("/api/members/tree/").status_code, 404)
        self.assertEqual(api(self.E.user).get("/api/members/tree/99999/").status_code, 404)

    def test_pending_user_gets_nothing(self):
        pending = make_member("Pend", login=True, status=MemberStatus.PENDING)
        self.assertEqual(api(pending.user).get("/api/members/tree/").status_code, 403)

    def test_contact_details_masked_for_hidden_people_in_tree(self):
        outsider = make_member("Hider", M, father=self.G1, mother=self.G2, hide_contact=True, mobile="9888888888")
        _, n = self.tree(self.E.user)
        self.assertIsNone(n["Hider"]["mobile"])
        _, n = self.tree(self.admin, f"/api/members/tree/{self.E.id}/")
        self.assertEqual(n["Hider"]["mobile"], "9888888888")


class SingleMemberAndEdgeCases(TestCase):
    def test_member_with_no_relatives_gets_a_tree_with_just_himself(self):
        m = make_member("Alone", login=True)
        r = api(m.user).get("/api/members/tree/")
        self.assertEqual([n["name"] for n in r.data["tree"]["nodes"]], ["Alone"])
        self.assertEqual(r.data["tree"]["edges"], [])

    def test_sibling_whose_parent_record_is_missing_is_not_lost_when_in_household(self):
        family, head = make_family_with_head("Head")
        brother = make_member("OrphanBrother", M, family=family)       # no father/mother links
        r = api(head.user).get("/api/members/tree/")
        self.assertIn("OrphanBrother", {n["name"] for n in r.data["tree"]["nodes"]})

    def test_spouse_stored_on_one_side_only_is_still_found(self):
        family, head = make_family_with_head("Head")
        wife = make_member("Wife", F, family=family)
        wife.spouse = head          # head.spouse stays empty
        wife.save()
        r = api(head.user).get("/api/members/tree/")
        nodes = {n["name"]: n for n in r.data["tree"]["nodes"]}
        self.assertEqual(nodes["Wife"]["relation_key"], "wife")
        self.assertTrue(any(e["type"] == "spouse" for e in r.data["tree"]["edges"]))

    def test_calculated_relation_label_is_still_returned_for_old_app_versions(self):
        family, head = make_family_with_head("Head")
        kid = make_member("Kid", M, family=family, father=head)
        r = api(head.user).get("/api/members/tree/")
        nodes = {n["name"]: n for n in r.data["tree"]["nodes"]}
        self.assertEqual(nodes["Kid"]["calculated_relation"], "Son")
        self.assertEqual(nodes["Kid"]["father_id"], head.id)


class MyFamilyHasRelationKeys(TestCase):
    def test_household_members_carry_relation_to_the_logged_in_member(self):
        family, head = make_family_with_head("Head")
        wife = make_member("Wife", F, family=family, spouse=head)
        head.spouse = wife
        head.save()
        kid = make_member("Kid", M, family=family, father=head, mother=wife)
        r = api(head.user).get("/api/members/my-family/")
        rows = {m["name"]: m for m in r.data["familyMembers"]}
        self.assertEqual(rows["Head"]["relation_key"], "self")
        self.assertEqual(rows["Wife"]["relation_key"], "wife")
        self.assertEqual(rows["Kid"]["relation_key"], "son")
        # and from the child's point of view
        kid.user = make_member("tmp", login=True).user
        kid.save()
        r = api(kid.user).get("/api/members/my-family/")
        rows = {m["name"]: m for m in r.data["familyMembers"]}
        self.assertEqual(rows["Head"]["relation_key"], "father")
        self.assertEqual(rows["Wife"]["relation_key"], "mother")
        self.assertEqual(rows["Kid"]["relation_key"], "self")


class TreeMeta(TestCase):
    def test_generations_counts_the_levels_shown(self):
        gp = make_member("Grandpa", M)
        dad = make_member("Dad", M, father=gp)
        fam, me = make_family_with_head("Me")
        me.father = dad
        me.save()
        kid = make_member("Kid", M, family=fam, father=me)
        r = api(me.user).get("/api/members/tree/")
        self.assertEqual(r.data["meta"]["generations"], 4)
        self.assertEqual(r.data["meta"]["people"], 4)
        self.assertEqual(r.data["meta"]["ego_name"], "Me")

    def test_single_person_is_one_generation(self):
        fam, me = make_family_with_head("Solo")
        self.assertEqual(api(me.user).get("/api/members/tree/").data["meta"]["generations"], 1)

    def test_spouse_is_the_same_generation(self):
        fam, me = make_family_with_head("Me")
        wife = make_member("Wife", F, family=fam, spouse=me)
        me.spouse = wife
        me.save()
        self.assertEqual(api(me.user).get("/api/members/tree/").data["meta"]["generations"], 1)


class DirectoryFilters(TestCase):
    def setUp(self):
        self.viewer = make_member("Viewer", login=True)
        self.a = make_member("Ashok Suthar", login=True, native_place="Gadha", occupation="Furniture business", gotra="Kashyap", blood_group="B+")
        self.b = make_member("Bhavna Mistry", login=True, native_place="Vijapur", occupation="Teacher", gotra="Bharadwaj", blood_group="O+")
        self.c = make_member("Hetal Suthar", login=True, city="Idar", occupation="Nurse")

    def names(self, qs=""):
        r = api(self.viewer.user).get(f"/api/members/all/{qs}")
        return {m["name"] for m in r.data["familyMembers"]} - {"Viewer"}

    def test_no_filter_returns_everyone(self):
        self.assertEqual(self.names(), {"Ashok Suthar", "Bhavna Mistry", "Hetal Suthar"})

    def test_by_village_matches_native_place_or_city_case_insensitive(self):
        self.assertEqual(self.names("?village=gadha"), {"Ashok Suthar"})
        self.assertEqual(self.names("?village=IDAR"), {"Hetal Suthar"})

    def test_by_occupation_gotra_blood(self):
        self.assertEqual(self.names("?occupation=teach"), {"Bhavna Mistry"})
        self.assertEqual(self.names("?gotra=kashyap"), {"Ashok Suthar"})
        self.assertEqual(self.names("?blood_group=o%2B"), {"Bhavna Mistry"})

    def test_free_text_search_checks_name_village_occupation(self):
        self.assertEqual(self.names("?q=suthar"), {"Ashok Suthar", "Hetal Suthar"})
        self.assertEqual(self.names("?q=vijapur"), {"Bhavna Mistry"})
        self.assertEqual(self.names("?q=furniture"), {"Ashok Suthar"})

    def test_filters_combine(self):
        self.assertEqual(self.names("?q=suthar&village=gadha"), {"Ashok Suthar"})
        self.assertEqual(self.names("?village=gadha&gotra=bharadwaj"), set())

    def test_admin_can_filter_too(self):
        r = api(make_admin()).get("/api/members/all/?q=bhavna")
        self.assertEqual({m["name"] for m in r.data["familyMembers"]}, {"Bhavna Mistry"})


class ProfileCompletion(TestCase):
    def test_percent_and_missing_fields(self):
        m = make_member("Full", login=True, gender="male", date_of_birth="1990-01-01", native_place="Gadha",
                        city="Idar", email="a@b.c", occupation="x", highest_qualification="BE",
                        blood_group="O+", address="somewhere")
        d = api(m.user).get("/api/members/me/status/").data
        self.assertEqual(d["completion"], {"percent": 100, "missing": []})
        self.assertEqual(d["village"], "Gadha")

    def test_missing_fields_listed(self):
        m = make_member("Part", login=True, gender="male", date_of_birth="1990-01-01", native_place="Gadha",
                        city="Idar", email="a@b.c", occupation="x", highest_qualification="BE")
        d = api(m.user).get("/api/members/me/status/").data["completion"]
        self.assertEqual(d["percent"], 80)
        self.assertEqual(d["missing"], ["blood_group", "address"])

    def test_empty_profile(self):
        m = make_member("Bare", login=True, gender=None)
        d = api(m.user).get("/api/members/me/status/").data["completion"]
        self.assertEqual(d["percent"], 10)       # only the name is filled


class BothSidesFilter(BigFamily):
    def test_maternal_false_hides_mothers_parents_and_her_siblings(self):
        _, n = self.tree(self.E.user, "/api/members/tree/?maternal=false")
        for hidden in ("MG1", "MG2", "Mama", "Masi"):
            self.assertNotIn(hidden, n, hidden)
        for shown in ("Father", "Mother", "G1", "G2", "Kaka", "Bua", "Wife", "Son"):
            self.assertIn(shown, n, shown)

    def test_default_keeps_both_sides(self):
        _, n = self.tree(self.E.user)
        for name in ("MG1", "Mama", "Masi"):
            self.assertIn(name, n)
