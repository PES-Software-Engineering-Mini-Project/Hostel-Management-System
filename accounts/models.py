from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class UserManager(BaseUserManager):
    """Creates users authenticated by college SRN instead of a username."""

    use_in_migrations = True

    def _create_user(self, srn, email, password, **extra_fields):
        if not srn:
            raise ValueError("The SRN must be set")
        if not email:
            raise ValueError("The email address must be set")
        if not password:
            raise ValueError("The password must be set")
        user = self.model(srn=srn.upper(), email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, srn, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.STUDENT)
        return self._create_user(srn, email, password, **extra_fields)

    def create_superuser(self, srn, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(srn, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        ADMIN = "admin", "Admin"

    username = None
    srn = models.CharField("SRN", max_length=13, unique=True)
    email = models.EmailField("email address", unique=True)
    contact_number = models.CharField(max_length=15)
    branch = models.CharField(max_length=30, blank=True)
    year_of_study = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(9)]
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    USERNAME_FIELD = "srn"
    REQUIRED_FIELDS = ["email", "first_name", "last_name", "contact_number"]

    objects = UserManager()

    def save(self, *args, **kwargs):
        self.srn = self.srn.upper()
        self.email = self.email.lower()
        super().save(*args, **kwargs)
