from django.db import models
from django.conf import settings
from members.constants import Community
from members.models import MemberStatus

User = settings.AUTH_USER_MODEL

# =======================
# USER PROFILE
# =======================
class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_profile"  # unique related_name
    )

    REGISTRATION_ROLE_CHOICES = (
        ("familyHead", "Family Head"),
        ("member", "Member"),
    )

    registration_role = models.CharField(
        max_length=30,
        choices=REGISTRATION_ROLE_CHOICES,
        default="member",
        blank=True
    )

    is_profile_completed = models.BooleanField(default=False)

    # ✅ SINGLE EDUCATION OBJECT (latest)
    @property
    def education(self):
        # Safe access to the OneToOne education_detail
        return getattr(self, "education_detail", None)


    def __str__(self):
        return f"{self.user.phone} - {self.registration_role}"


# =======================
# PERSONAL DETAIL (SINGLE)
# =======================
class PersonalDetail(models.Model):
    profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="personal"
    )

    full_name = models.CharField(max_length=255, blank=True, default="")
    country_code = models.CharField(max_length=5, default="+91")
    phone = models.CharField(max_length=20, blank=True, default="")
    nickname = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    dob = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    native_place = models.CharField(max_length=100, blank=True, null=True)
    current_city = models.CharField(max_length=100, blank=True, null=True)
    profile_image = models.ImageField(
        upload_to="profile/",
        null=True,
        blank=True
    )
    community = models.IntegerField(
        choices=Community.choices,
        null=True,
        blank=True  
    )
    status = models.CharField(
        max_length=20,
        choices=MemberStatus.choices,
        default=MemberStatus.PENDING
    )
    
    def __str__(self):
        return self.full_name or f"Detail for {self.profile.user.phone}"


# =======================
# EDUCATION DETAIL (FK)
# =======================
class EducationDetail(models.Model):
    profile = models.OneToOneField( # Changed from ForeignKey
        UserProfile,
        on_delete=models.CASCADE,
        related_name="education_detail" # Changed name to avoid property conflict
    )

    qualification = models.CharField(max_length=100, blank=True, null=True)
    institution = models.CharField(max_length=255, blank=True, null=True)
    field = models.CharField(max_length=100, blank=True, null=True)
    start_year = models.IntegerField(blank=True, null=True)
    end_year = models.IntegerField(blank=True, null=True)
    currently_studying = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.qualification} - {self.profile.user.phone}"


# =======================
# JOB DETAIL (SINGLE)
# =======================
class JobDetail(models.Model):
    profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="job"
    )

    occupation_type = models.CharField(max_length=100, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    income_range = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.occupation_type} for {self.profile.user.phone}"


# =======================
# FAMILY (for profiles)
# =======================
class Family(models.Model):
    head = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profiles_managed_family",  # unique related_name
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Families"

    def __str__(self):
        return str(self.id)


# =======================
# MEMBER (for profiles)
# =======================
class Member(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles_member_set"  # unique related_name
    )
    family = models.ForeignKey(
        Family,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members"
    )
    mobile = models.CharField(max_length=20)
    country_code = models.CharField(max_length=5, default="+91")
    name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=20,
        choices=(
            ("member", "Member"),
            ("familyHead", "Family Head"),
            ("admin", "Admin")
        ),
        default="member"
    )
    status = models.CharField(
        max_length=20,
        choices=(
            ("pending", "Pending"),
            ("active", "Active"),
            ("rejected", "Rejected"),
            ("accepted", "Accepted")
        ),
        default="pending"
    )

   
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["country_code", "mobile", "family"],
                name="unique_member_per_family_profiles",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.role}"
