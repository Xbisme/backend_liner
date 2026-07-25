"""UserManager — email is optional (social-only accounts) and normalized."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import BaseUserManager

if TYPE_CHECKING:
    from apps.accounts.models import User


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create(
        self,
        email: str | None,
        password: str | None,
        display_name: str,
        **extra: Any,
    ) -> User:
        normalized = self.normalize_email(email).lower() if email else None
        user = self.model(email=normalized, display_name=display_name, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password"], validate_unique=False)
        user.save(using=self._db)
        return user

    def create_user(
        self,
        email: str | None = None,
        password: str | None = None,
        display_name: str = "",
        **extra: Any,
    ) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, display_name, **extra)

    def create_superuser(
        self,
        email: str,
        password: str,
        display_name: str = "",
        **extra: Any,
    ) -> User:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not email:
            raise ValueError("Superuser must have an email.")
        if not password:
            raise ValueError("Superuser must have a password.")
        return self._create(email, password, display_name or "Admin", **extra)
