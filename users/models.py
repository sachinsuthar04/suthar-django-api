from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, phone=None, password=None, email=None, **extra_fields):
        role = extra_fields.get("role", "member")

        if role == "admin" and not email:
            raise ValueError("Admin must have an email.")

        if role == "member" and not phone:
            raise ValueError("Member must have a phone number.")

        user = self.model(
            phone=phone,
            email=email,
            country_code=extra_fields.get("country_code", "+91"),
            **extra_fields,
        )

        if role == "admin":
            if not password:
                raise ValueError("Admin must have a password.")
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("member", "Member"),
    )

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)

    # ✅ NEW FIELD
    country_code = models.CharField(max_length=5, default="+91")

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Admin login via email
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            # ✅ phone + country_code unique together
            models.UniqueConstraint(
                fields=["country_code", "phone"],
                name="unique_country_phone_user",
            )
        ]

    def __str__(self):
        return self.email if self.role == "admin" else f"{self.country_code}{self.phone}"
