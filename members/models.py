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
    # Core Level
    SELF = "self", "Self"
    SPOUSE = "spouse", "Spouse"
    
    # Parents
    FATHER = "father", "Father"
    MOTHER = "mother", "Mother"
    
    # Grandparents
    GRANDFATHER = "grandfather", "Grandfather"
    GRANDMOTHER = "grandmother", "Grandmother"
    
    # Siblings
    BROTHER = "brother", "Brother"
    SISTER = "sister", "Sister"
    
    # Children
    SON = "son", "Son"
    DAUGHTER = "daughter", "Daughter"
    
    # Extended (Optional but recommended for a complete tree)
    UNCLE = "uncle", "Uncle"
    BUA = "bua", "Bua"
    
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
        on_delete=models.SET_NULL,  # deleting a login must never delete the family
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
    spouse = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="spouse_of"
    )
    father = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children_as_father",
        help_text="Father of the member"
    )
    mother = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children_as_mother",
        help_text="Mother of the member"
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

    profile_image = models.ImageField(
    upload_to="profile/member/",
    null=True,
    blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    gotra = models.CharField(max_length=100, null=True, blank=True)
    native_place = models.CharField(max_length=100, null=True, blank=True)

    # ---- Additional Info ----
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    highest_qualification = models.CharField(max_length=100, null=True, blank=True)

    # ---- System ----
    created_at = models.DateTimeField(auto_now_add=True)
    profile_completed = models.BooleanField(default=False)

    # ---- Life status ----
    is_alive = models.BooleanField(default=True)
    date_of_death = models.DateField(null=True, blank=True)

    # ---- Privacy ----
    hide_contact = models.BooleanField(
        default=False,
        help_text="Hide mobile/email/address from members outside the household",
    )

    # ---- Approval history ----
    status_reason = models.TextField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    status_changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["country_code", "mobile", "family"],
                name="unique_member_country_mobile_per_family",
            ),
            # exactly ONE family head per family (DB-level guarantee)
            models.UniqueConstraint(
                fields=["family"],
                condition=models.Q(role="familyHead"),
                name="unique_family_head_per_family",
            ),
        ]


    def __str__(self):
        return f"{self.name} - {self.role}"

    @property
    def family_display_id(self):
        if self.family and self.family.head_id:
            return f"F_{self.family.head_id}"
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

# -------------------------------------------------
# RELATIONSHIP REQUEST
# -------------------------------------------------
class RelationshipRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"

class RelationshipRequest(models.Model):
    sender = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="sent_relationship_requests")
    receiver = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="received_relationship_requests")
    proposed_relation = models.CharField(max_length=20, choices=MemberRelation.choices)
    status = models.CharField(max_length=20, choices=RelationshipRequestStatus.choices, default=RelationshipRequestStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "receiver", "status"],
                condition=models.Q(status="pending"),
                name="unique_pending_request_between_members",
            )
        ]

    def __str__(self):
        return f"{self.sender.name} -> {self.receiver.name} ({self.proposed_relation}) [{self.status}]"


# -------------------------------------------------
# PROFILE CHANGE REQUEST (key-field edits after approval)
# -------------------------------------------------
class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


class ProfileChangeRequest(models.Model):
    """
    Edits to key identity fields (name, gender, date of birth, gotra) of an
    already-approved member are not applied directly: they wait here for an
    admin.  `changes` = {"field": {"old": ..., "new": ...}} (JSON safe values).
    """
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="change_requests")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    changes = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reason = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Change #{self.id} for {self.member_id} [{self.status}]"


# -------------------------------------------------
# FAMILY HEAD REQUEST (new household / transfer of headship)
# -------------------------------------------------
class HeadRequestKind(models.TextChoices):
    NEW_HOUSEHOLD = "new_household", "New household"
    TRANSFER = "transfer", "Transfer headship"


class FamilyHeadRequest(models.Model):
    kind = models.CharField(max_length=20, choices=HeadRequestKind.choices)
    # NEW_HOUSEHOLD: the member who wants to head a new family
    # TRANSFER: the member who will become the new head
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="head_requests")
    family = models.ForeignKey(Family, on_delete=models.CASCADE, null=True, blank=True, related_name="head_requests")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reason = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "kind"],
                condition=models.Q(status="pending"),
                name="unique_pending_head_request_per_member_kind",
            )
        ]

    def __str__(self):
        return f"{self.kind} for {self.member_id} [{self.status}]"


# -------------------------------------------------
# AUDIT LOG
# -------------------------------------------------
class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    action = models.CharField(max_length=60)
    entity = models.CharField(max_length=40)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.entity}#{self.entity_id}"
