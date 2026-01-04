from django.db import models, transaction
from django.conf import settings
from .constants import Community

User = settings.AUTH_USER_MODEL

# -------------------------------------------------
# ENUMS
# -------------------------------------------------
class MemberStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    REJECTED = "rejected", "Rejected"

class MemberRole(models.TextChoices):
    MEMBER = "member", "Member"
    FAMILY_HEAD = "familyHead", "Family Head"
    ADMIN = "admin", "Admin"

class MemberRelation(models.TextChoices):
    SELF = "self", "Self"
    SPOUSE = "spouse", "Spouse"
    SON = "son", "Son"
    DAUGHTER = "daughter", "Daughter"
    FATHER = "father", "Father"
    MOTHER = "mother", "Mother"
    BROTHER = "brother", "Brother"
    SISTER = "sister", "Sister"
    OTHER = "other", "Other"

class MemberGender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"

# -------------------------------------------------
# FAMILY
# -------------------------------------------------
class Family(models.Model):
    head = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="members_managed_family",  # unique related_name
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Families"

    def __str__(self):
        return str(self.id)

# -------------------------------------------------
# MEMBER
# -------------------------------------------------
class Member(models.Model):
    """Main Member Table"""

    # ---- Community ----
    community = models.IntegerField(
        choices=Community.choices,
        default=Community.SUTHAR,
        null=True,
        blank=True
    )

    # ---- Main Links ----
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members_member_set"  # unique related_name
    )

    family = models.ForeignKey(
        Family,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members"
    )

    # ---- Identity ----
    country_code = models.CharField(max_length=5, default="+91")
    mobile = models.CharField(max_length=20)
    name = models.CharField(max_length=100)

    # ---- Role & Status ----
    role = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
        default=MemberRole.MEMBER
    )
    status = models.CharField(
        max_length=20,
        choices=MemberStatus.choices,
        default=MemberStatus.PENDING
    )
    relation = models.CharField(
        max_length=20,
        choices=MemberRelation.choices,
        null=True,
        blank=True
    )

    # ---- Profile Details ----
    gender = models.CharField(
        max_length=10,
        choices=MemberGender.choices,
        null=True,
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    gotra = models.CharField(max_length=100, null=True, blank=True)
    profile_image = models.TextField(null=True, blank=True)
    native_place = models.CharField(max_length=100, null=True, blank=True)

    # ---- Additional Info ----
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    highest_qualification = models.CharField(max_length=100, null=True, blank=True)
    spouse_id = models.CharField(max_length=100, null=True, blank=True)

    # ---- System ----
    created_at = models.DateTimeField(auto_now_add=True)
    profile_completed = models.BooleanField(default=False)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["country_code", "mobile", "family"],
                name="unique_member_country_mobile_per_family",
            )
        ]


    def __str__(self):
        return f"{self.name} - {self.role}"

    @property
    def family_display_id(self):
        if self.family and self.family.head:
            return f"F_{self.family.head.id}"
        return "Unassigned"

    # -------------------------------------------------
    # FAMILY HEAD SWITCH LOGIC
    # -------------------------------------------------
    def make_family_head(self):
        """
        Make this member the Family Head.
        Old head (if any) becomes a normal member.
        """
        if not self.family:
            raise ValueError("Member does not belong to a family")
        if not self.user:
            raise ValueError("Family head must be linked to a user")

        with transaction.atomic():
            family = self.family

            # Old head → member
            old_head = Member.objects.filter(
                family=family,
                role=MemberRole.FAMILY_HEAD
            ).exclude(id=self.id).first()

            if old_head:
                old_head.role = MemberRole.MEMBER
                old_head.save(update_fields=["role"])

            # New head
            self.role = MemberRole.FAMILY_HEAD
            self.save(update_fields=["role"])

            # Update Family table
            family.head = self.user
            family.save(update_fields=["head"])
