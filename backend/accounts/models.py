from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "user", "User"
        MECHANIC = "mechanic", "Mechanic"
        REVIEWER = "reviewer", "Reviewer"
        ADMIN = "admin", "Admin"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        ROMAN_URDU = "roman_ur", "Roman Urdu"
        URDU = "ur", "Urdu"

    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)

    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    city = models.CharField(max_length=60, blank=True)
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.USER
    )
    language = models.CharField(
        max_length=10, choices=Language.choices, default=Language.ENGLISH
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class MechanicProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True,
        related_name="mechanic_profile",
    )
    workshop_name = models.CharField(max_length=150)
    address = models.CharField(max_length=250, blank=True)
    city = models.CharField(max_length=60, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    specialization = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    honesty_score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.workshop_name
