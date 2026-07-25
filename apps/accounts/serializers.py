"""Serializers = validation + contract shape enforcement (Principle II)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.models import SocialIdentity, User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    display_name = serializers.CharField(max_length=150)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class SocialLoginSerializer(serializers.Serializer):
    # Provider outside the enum → VALIDATION_ERROR (not SOCIAL_TOKEN_INVALID).
    provider = serializers.ChoiceField(choices=SocialIdentity.Provider.values)
    id_token = serializers.CharField()


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    auth_provider = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="date_joined", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "avatar_url",
            "auth_provider",
            "created_at",
        ]

    def get_avatar_url(self, obj: User) -> str | None:
        return None  # No avatar feature in BE-001.

    def get_auth_provider(self, obj: User) -> str:
        if obj.has_usable_password():
            return "email"
        identity = obj.social_identities.first()
        return identity.provider if identity else "email"


def auth_token_payload(user: User, tokens: dict[str, Any]) -> dict[str, Any]:
    """Build the AuthTokenResponse body (contract shape)."""
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": tokens["expires_in"],
        "user": UserSerializer(user).data,
    }
