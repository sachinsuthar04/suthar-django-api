from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from members.models import Member, MemberGender, MemberRole, Family
from members.utils import get_relationship, heal_family_relations
from members.views import FamilyTreeView
import datetime

User = get_user_model()


class RelationshipResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="9999999990", country_code="+91", password="123")
        self.family = Family.objects.create(head=self.user)
        
        self.sachin = Member.objects.create(
            name="Sachin", 
            gender=MemberGender.MALE, 
            family=self.family,
            mobile="12345",
            role=MemberRole.FAMILY_HEAD
        )
        self.juee = Member.objects.create(
            name="Juee", 
            gender=MemberGender.FEMALE, 
            family=self.family,
            mobile="123456"
        )
        # Link Spouses
        self.sachin.spouse = self.juee
        self.sachin.save()
        self.juee.spouse = self.sachin
        self.juee.save()

        self.son = Member.objects.create(
            name="Son", 
            gender=MemberGender.MALE, 
            family=self.family,
            father=self.sachin,
            mother=self.juee,
            mobile="1234567"
        )
        self.daughter = Member.objects.create(
            name="Daughter", 
            gender=MemberGender.FEMALE, 
            family=self.family,
            father=self.sachin,
            mother=self.juee,
            mobile="12345678"
        )

    def test_spouse_relationship(self):
        self.assertEqual(get_relationship(self.sachin, self.juee), "Wife")
        self.assertEqual(get_relationship(self.juee, self.sachin), "Husband")

    def test_parent_child_relationship(self):
        self.assertEqual(get_relationship(self.sachin, self.son), "Son")
        self.assertEqual(get_relationship(self.juee, self.son), "Son")
        self.assertEqual(get_relationship(self.sachin, self.daughter), "Daughter")

        self.assertEqual(get_relationship(self.son, self.sachin), "Father")
        self.assertEqual(get_relationship(self.son, self.juee), "Mother")

    def test_sibling_relationship(self):
        self.assertEqual(get_relationship(self.son, self.daughter), "Sister")
        self.assertEqual(get_relationship(self.daughter, self.son), "Brother")

    def test_grandparent_relationship(self):
        grandson = Member.objects.create(
            name="Grandson",
            gender=MemberGender.MALE,
            family=self.family,
            father=self.son
        )
        self.assertEqual(get_relationship(self.sachin, grandson), "Grandson")
        self.assertEqual(get_relationship(grandson, self.sachin), "Grandfather")
        self.assertEqual(get_relationship(self.juee, grandson), "Grandson")
        self.assertEqual(get_relationship(grandson, self.juee), "Grandmother")


class TenMemberFamilyTreeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="9510981420", country_code="+91", password="123")
        self.family = Family.objects.create(head=self.user)

        # 1. Family Head (Sachin)
        self.head = Member.objects.create(
            user=self.user,
            family=self.family,
            name="Head Member",
            gender=MemberGender.MALE,
            role=MemberRole.FAMILY_HEAD,
            mobile="9510981420",
            date_of_birth=datetime.date(1990, 1, 1)
        )

        # 2. Spouse (Wife)
        self.spouse = Member.objects.create(
            family=self.family,
            name="Spouse Member",
            gender=MemberGender.FEMALE,
            relation="spouse",
            mobile="9510981421",
            date_of_birth=datetime.date(1992, 2, 2)
        )

        # 3. Father
        self.father = Member.objects.create(
            family=self.family,
            name="Father Member",
            gender=MemberGender.MALE,
            relation="father",
            mobile="9510981422",
            date_of_birth=datetime.date(1960, 3, 3)
        )

        # 4. Mother
        self.mother = Member.objects.create(
            family=self.family,
            name="Mother Member",
            gender=MemberGender.FEMALE,
            relation="mother",
            mobile="9510981423",
            date_of_birth=datetime.date(1965, 4, 4)
        )

        # 5. Grandfather
        self.grandfather = Member.objects.create(
            family=self.family,
            name="Grandfather Member",
            gender=MemberGender.MALE,
            relation="grandfather",
            mobile="9510981424",
            date_of_birth=datetime.date(1935, 5, 5)
        )

        # 6. Grandmother
        self.grandmother = Member.objects.create(
            family=self.family,
            name="Grandmother Member",
            gender=MemberGender.FEMALE,
            relation="grandmother",
            mobile="9510981425",
            date_of_birth=datetime.date(1940, 6, 6)
        )

        # 7. Brother
        self.brother = Member.objects.create(
            family=self.family,
            name="Brother Member",
            gender=MemberGender.MALE,
            relation="brother",
            mobile="9510981426",
            date_of_birth=datetime.date(1994, 7, 7)
        )

        # 8. Sister
        self.sister = Member.objects.create(
            family=self.family,
            name="Sister Member",
            gender=MemberGender.FEMALE,
            relation="sister",
            mobile="9510981427",
            date_of_birth=datetime.date(1996, 8, 8)
        )

        # 9. Son
        self.son = Member.objects.create(
            family=self.family,
            name="Son Member",
            gender=MemberGender.MALE,
            relation="son",
            mobile="9510981428",
            date_of_birth=datetime.date(2018, 9, 9)
        )

        # 10. Daughter
        self.daughter = Member.objects.create(
            family=self.family,
            name="Daughter Member",
            gender=MemberGender.FEMALE,
            relation="daughter",
            mobile="9510981429",
            date_of_birth=datetime.date(2020, 10, 10)
        )

    def test_heal_family_relations(self):
        heal_family_relations(self.family)
        
        self.head.refresh_from_db()
        self.spouse.refresh_from_db()
        self.father.refresh_from_db()
        self.mother.refresh_from_db()
        self.grandfather.refresh_from_db()
        self.grandmother.refresh_from_db()
        self.brother.refresh_from_db()
        self.sister.refresh_from_db()
        self.son.refresh_from_db()
        self.daughter.refresh_from_db()

        # Check Head links
        self.assertEqual(self.head.spouse_id, self.spouse.id)
        self.assertEqual(self.spouse.spouse_id, self.head.id)
        self.assertEqual(self.head.father_id, self.father.id)
        self.assertEqual(self.head.mother_id, self.mother.id)

        # Check Father & Mother links
        self.assertEqual(self.father.spouse_id, self.mother.id)
        self.assertEqual(self.mother.spouse_id, self.father.id)
        self.assertEqual(self.father.father_id, self.grandfather.id)
        self.assertEqual(self.father.mother_id, self.grandmother.id)

        # Check Grandparents links
        self.assertEqual(self.grandfather.spouse_id, self.grandmother.id)
        self.assertEqual(self.grandmother.spouse_id, self.grandfather.id)

        # Check Siblings links
        self.assertEqual(self.brother.father_id, self.father.id)
        self.assertEqual(self.brother.mother_id, self.mother.id)
        self.assertEqual(self.sister.father_id, self.father.id)
        self.assertEqual(self.sister.mother_id, self.mother.id)

        # Check Children links
        self.assertEqual(self.son.father_id, self.head.id)
        self.assertEqual(self.son.mother_id, self.spouse.id)
        self.assertEqual(self.daughter.father_id, self.head.id)
        self.assertEqual(self.daughter.mother_id, self.spouse.id)

    def test_family_tree_api_view(self):
        factory = APIRequestFactory()
        request = factory.get('/api/members/tree/')
        force_authenticate(request, user=self.user)

        view = FamilyTreeView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data.get("success"))
        
        tree = data.get("tree", {})
        nodes = tree.get("nodes", [])
        edges = tree.get("edges", [])

        # All 10 members MUST be in nodes
        self.assertEqual(len(nodes), 10)
        node_ids = {node["id"] for node in nodes}
        expected_ids = {
            self.head.id, self.spouse.id, self.father.id, self.mother.id,
            self.grandfather.id, self.grandmother.id, self.brother.id,
            self.sister.id, self.son.id, self.daughter.id
        }
        self.assertEqual(node_ids, expected_ids)

        # Check edges exist
        self.assertTrue(len(edges) >= 8)
