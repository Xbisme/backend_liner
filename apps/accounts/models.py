"""Account models: User (optional email) and SocialIdentity."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.accounts.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    # Integer pk to honor the API contract (openapi.yaml User.id: integer).
    email = models.EmailField(unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        db_table = "accounts_user"

    def __str__(self) -> str:
        return self.email or f"user#{self.pk}"


class SocialIdentity(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="social_identities"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    subject_id = models.CharField(max_length=255)
    email_at_provider = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_social_identity"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "subject_id"],
                name="uniq_provider_subject",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.subject_id}"
