"""Village list (35 Kantha Sattavis villages) and the admin village API."""
from django.test import TestCase

from dashboard.models import Village
from members.testing import api, make_admin, make_member


class SeededVillages(TestCase):
    def test_35_kantha_sattavis_villages_are_seeded_in_poster_order(self):
        active = list(Village.objects.filter(is_active=True).order_by("number"))
        self.assertEqual(len(active), 35)
        self.assertEqual((active[0].name, active[0].name_gu), ("Aglod", "આગલોડ"))
        self.assertEqual((active[12].number, active[12].name), (13, "Gadha"))
        self.assertEqual((active[-1].number, active[-1].name_gu), (35, "વકતાપુર"))

    def test_public_list_only_shows_active_villages_with_gujarati_name(self):
        Village.objects.create(name="Old place", is_active=False, number=99)
        member = make_member("M", login=True)
        r = api(member.user).get("/api/home/villages/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["village"]), 35)
        self.assertEqual(r.data["village"][0], {"id": r.data["village"][0]["id"], "name": "Aglod", "name_gu": "આગલોડ", "number": 1})


class AdminVillageApi(TestCase):
    def setUp(self):
        self.admin = api(make_admin())

    def test_only_admin(self):
        member = make_member("M", login=True, status="active")
        self.assertEqual(api(member.user).get("/api/home/admin/villages/").status_code, 403)
        self.assertEqual(api(member.user).post("/api/home/admin/villages/", {"name": "X"}).status_code, 403)

    def test_list_counts_members_by_english_or_gujarati_name(self):
        make_member("A", native_place="Gadha")
        make_member("B", native_place="ગઢા")
        r = self.admin.get("/api/home/admin/villages/")
        self.assertEqual((r.data["total"], r.data["active"]), (35, 35))
        gadha = next(v for v in r.data["village"] if v["name"] == "Gadha")
        self.assertEqual(gadha["memberCount"], 2)

    def test_add_gets_next_number_and_rejects_duplicates(self):
        r = self.admin.post("/api/home/admin/villages/", {"name": "Navo Gam", "name_gu": "નવો ગામ"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["village"]["number"], 36)
        r = self.admin.post("/api/home/admin/villages/", {"name": "gadha"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_rename_moves_members_native_place(self):
        m = make_member("A", native_place="Falu")
        v = Village.objects.get(name="Falu")
        r = self.admin.patch(f"/api/home/admin/villages/{v.id}/", {"name": "Phalu"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        m.refresh_from_db()
        self.assertEqual(m.native_place, "Phalu")

    def test_delete_unused_removes_used_only_switches_off(self):
        make_member("A", native_place="Hapa")
        hapa = Village.objects.get(name="Hapa")
        ilol = Village.objects.get(name="Ilol")
        r = self.admin.delete(f"/api/home/admin/villages/{hapa.id}/")
        self.assertFalse(r.data["deleted"])
        hapa.refresh_from_db()
        self.assertFalse(hapa.is_active)
        r = self.admin.delete(f"/api/home/admin/villages/{ilol.id}/")
        self.assertTrue(r.data["deleted"])
        self.assertFalse(Village.objects.filter(id=ilol.id).exists())
