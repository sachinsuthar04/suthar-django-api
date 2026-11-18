"""Pure unit tests of the relation engine - no database."""
from django.test import SimpleTestCase

from members.services.kinship import KinshipGraph, Person, relation_between, relations_from


def P(id_, gender, father=None, mother=None, spouse=None):
    return Person(id_, gender, father, mother, spouse)


class Big(SimpleTestCase):
    """
    Paternal side           Maternal side             Ego's wife side
    G1(m)=G2(f)             MG1(m)=MG2(f)             WF(m)=WM(f)
     |- F(m)=M(f)  <---      |- M(f)                   |- W(f)  WB(m)  WS(f)
     |- K(m)=KK(f)  C(m)     |- MM(m)=MMW(f)
     |- B(f)=BH(m)          |- MS(f)=MSH(m)
    ego E(m)=W ; Bro(m)=BW ; Sis(f)=SH ; children S(m)=DIL, D(f); grandchild GS
    """

    def setUp(self):
        ids = dict(
            G1=1, G2=2, F=3, M=4, K=5, KK=6, B=7, BH=8, C=9,
            MG1=10, MG2=11, MM=12, MMW=13, MS=14, MSH=15,
            E=20, Bro=21, BW=22, Sis=23, SH=24, N=25,
            WF=30, WM=31, W=32, WB=33, WS=34,
            S=40, D=41, DIL=42, GS=43,
        )
        self.i = ids
        i = ids
        people = [
            P(i["G1"], "male", spouse=i["G2"]), P(i["G2"], "female", spouse=i["G1"]),
            P(i["F"], "male", i["G1"], i["G2"], spouse=i["M"]),
            P(i["M"], "female", i["MG1"], i["MG2"], spouse=i["F"]),
            P(i["K"], "male", i["G1"], i["G2"], spouse=i["KK"]),
            P(i["KK"], "female", spouse=i["K"]),
            P(i["B"], "female", i["G1"], i["G2"], spouse=i["BH"]),
            P(i["BH"], "male", spouse=i["B"]),
            P(i["C"], "male", i["K"], i["KK"]),
            P(i["MG1"], "male", spouse=i["MG2"]), P(i["MG2"], "female", spouse=i["MG1"]),
            P(i["MM"], "male", i["MG1"], i["MG2"], spouse=i["MMW"]),
            P(i["MMW"], "female", spouse=i["MM"]),
            P(i["MS"], "female", i["MG1"], i["MG2"], spouse=i["MSH"]),
            P(i["MSH"], "male", spouse=i["MS"]),
            P(i["E"], "male", i["F"], i["M"], spouse=i["W"]),
            P(i["Bro"], "male", i["F"], i["M"], spouse=i["BW"]),
            P(i["BW"], "female", spouse=i["Bro"]),
            P(i["Sis"], "female", i["F"], i["M"], spouse=i["SH"]),
            P(i["SH"], "male", spouse=i["Sis"]),
            P(i["N"], "female", i["SH"], i["Sis"]),
            P(i["WF"], "male", spouse=i["WM"]), P(i["WM"], "female", spouse=i["WF"]),
            P(i["W"], "female", i["WF"], i["WM"], spouse=i["E"]),
            P(i["WB"], "male", i["WF"], i["WM"]),
            P(i["WS"], "female", i["WF"], i["WM"]),
            P(i["S"], "male", i["E"], i["W"], spouse=i["DIL"]),
            P(i["D"], "female", i["E"], i["W"]),
            P(i["DIL"], "female", spouse=i["S"]),
            P(i["GS"], "male", i["S"], i["DIL"]),
        ]
        self.g = KinshipGraph(people)

    def key(self, ego, target):
        return relation_between(self.g, self.i[ego], self.i[target]).key

    # ---- from the ego's own point of view -------------------------------
    def test_self(self):
        self.assertEqual(self.key("E", "E"), "self")

    def test_direct_family(self):
        for target, expected in [
            ("F", "father"), ("M", "mother"), ("W", "wife"),
            ("S", "son"), ("D", "daughter"),
            ("Bro", "brother"), ("Sis", "sister"),
        ]:
            self.assertEqual(self.key("E", target), expected, target)

    def test_grandparents_both_sides(self):
        for target, expected in [
            ("G1", "grandfather"), ("G2", "grandmother"),
            ("MG1", "grandfather"), ("MG2", "grandmother"),
        ]:
            self.assertEqual(self.key("E", target), expected, target)

    def test_grandchild(self):
        self.assertEqual(self.key("E", "GS"), "grandson")

    def test_fathers_side_uncle_aunt(self):
        self.assertEqual(self.key("E", "K"), "kaka")
        self.assertEqual(self.key("E", "KK"), "kaki")
        self.assertEqual(self.key("E", "B"), "bua")
        self.assertEqual(self.key("E", "BH"), "fua")

    def test_mothers_side_uncle_aunt(self):
        self.assertEqual(self.key("E", "MM"), "mama")
        self.assertEqual(self.key("E", "MMW"), "mami")
        self.assertEqual(self.key("E", "MS"), "masi")
        self.assertEqual(self.key("E", "MSH"), "masa")

    def test_cousin(self):
        self.assertEqual(self.key("E", "C"), "cousin_brother")

    def test_nephew_niece(self):
        self.assertEqual(self.key("E", "N"), "niece")

    def test_siblings_spouses(self):
        self.assertEqual(self.key("E", "BW"), "bhabhi")
        self.assertEqual(self.key("E", "SH"), "jija")

    def test_in_laws_of_a_husband(self):
        self.assertEqual(self.key("E", "WF"), "father_in_law")
        self.assertEqual(self.key("E", "WM"), "mother_in_law")
        self.assertEqual(self.key("E", "WB"), "saala")
        self.assertEqual(self.key("E", "WS"), "saali")

    def test_children_in_law(self):
        self.assertEqual(self.key("E", "DIL"), "daughter_in_law")

    # ---- the SAME graph from other people's point of view ---------------
    def test_wife_view_in_laws(self):
        self.assertEqual(self.key("W", "E"), "husband")
        self.assertEqual(self.key("W", "F"), "father_in_law")
        self.assertEqual(self.key("W", "M"), "mother_in_law")
        self.assertEqual(self.key("W", "Bro"), "devar")
        self.assertEqual(self.key("W", "Sis"), "nanand")
        self.assertEqual(self.key("W", "WB"), "brother")

    def test_son_view(self):
        """The 'son logs in' case from the requirements."""
        self.assertEqual(self.key("S", "E"), "father")
        self.assertEqual(self.key("S", "W"), "mother")
        self.assertEqual(self.key("S", "F"), "grandfather")
        self.assertEqual(self.key("S", "G1"), "great_grandfather")
        self.assertEqual(self.key("S", "Bro"), "kaka")      # father's brother
        self.assertEqual(self.key("S", "Sis"), "bua")       # father's sister
        self.assertEqual(self.key("S", "WB"), "mama")       # mother's brother
        self.assertEqual(self.key("S", "WS"), "masi")       # mother's sister
        self.assertEqual(self.key("S", "D"), "sister")
        self.assertEqual(self.key("S", "DIL"), "wife")
        self.assertEqual(self.key("S", "GS"), "son")

    def test_father_view_of_siblings_children(self):
        self.assertEqual(self.key("K", "E"), "nephew")
        self.assertEqual(self.key("E", "K"), "kaka")
        self.assertEqual(self.key("C", "E"), "cousin_brother")

    def test_far_relative_is_generic(self):
        self.assertEqual(self.key("WF", "G1"), "relative")
        self.assertEqual(self.key("W", "K"), "in_law")

    def test_labels_are_english_text(self):
        r = relation_between(self.g, self.i["E"], self.i["WB"])
        self.assertEqual((r.key, r.label), ("saala", "Saala"))

    def test_relations_from_covers_everyone(self):
        rels = relations_from(self.g, self.i["E"])
        self.assertEqual(set(rels), set(self.g.persons))
        self.assertEqual(rels[self.i["E"]].key, "self")


class EdgeCases(SimpleTestCase):
    def test_half_sibling_is_sibling(self):
        g = KinshipGraph([
            P(1, "male"), P(2, "female"), P(3, "female"),
            P(10, "male", 1, 2), P(11, "female", 1, 3),
        ])
        self.assertEqual(relation_between(g, 10, 11).key, "sister")

    def test_step_mother(self):
        g = KinshipGraph([
            P(1, "male", spouse=3), P(2, "female"), P(3, "female", spouse=1),
            P(10, "male", 1, 2),
        ])
        # 3 is father's current wife but NOT ego's mother
        self.assertEqual(relation_between(g, 10, 3).key, "stepmother")

    def test_one_sided_spouse_link_is_symmetric(self):
        g = KinshipGraph([P(1, "male", spouse=2), P(2, "female")])
        self.assertEqual(relation_between(g, 2, 1).key, "husband")
        self.assertEqual(relation_between(g, 1, 2).key, "wife")

    def test_unknown_gender_gets_neutral_label(self):
        g = KinshipGraph([P(1, "male"), P(2, None, 1, None)])
        self.assertEqual(relation_between(g, 1, 2).key, "child")

    def test_gender_inferred_from_parent_slot(self):
        g = KinshipGraph([P(1, None), P(2, "female"), P(3, "male", 1, 2)])
        # gender of 1 unknown but he is stored as father_id of 3 -> father
        self.assertEqual(relation_between(g, 3, 1).key, "father")

    def test_sibling_without_known_parents_is_not_linked(self):
        g = KinshipGraph([P(1, "male"), P(2, "male")])
        self.assertEqual(relation_between(g, 1, 2).key, "relative")

    def test_unknown_ids(self):
        g = KinshipGraph([P(1, "male")])
        self.assertEqual(relation_between(g, 1, 999).key, "relative")

    def test_corrupt_cycle_does_not_hang(self):
        g = KinshipGraph([P(1, "male", 2), P(2, "male", 1)])
        self.assertIn(relation_between(g, 1, 2).key, {"father", "son", "relative"})

    def test_great_grandparent_and_great_grandchild(self):
        g = KinshipGraph([
            P(1, "male"), P(2, "male", 1), P(3, "male", 2), P(4, "male", 3),
        ])
        self.assertEqual(relation_between(g, 4, 1).key, "great_grandfather")
        self.assertEqual(relation_between(g, 1, 4).key, "great_grandson")
