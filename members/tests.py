from django.test import TestCase
from members.models import Member, MemberGender, Family
from members.utils import get_relationship
from django.contrib.auth import get_user_model

User = get_user_model()

class RelationshipResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", password="123")
        self.family = Family.objects.create(head=self.user)
        
        self.sachin = Member.objects.create(
            name="Sachin", 
            gender=MemberGender.MALE, 
            family=self.family,
            mobile="12345"
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
