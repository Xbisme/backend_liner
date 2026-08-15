"""Thin auth + account views — delegate to serializers/services (Principle III)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import (
    LoginSerializer,
    RefreshSerializer,
    RegisterSerializer,
    SocialLoginSerializer,
    UserSerializer,
    auth_token_payload,
)
from apps.accounts.services import social, tokens
from core.errors import ErrorCode
from core.exceptions import AppError
from core.throttling import AuthRateThrottle


class RegisterView(APIView):
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        email = data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise AppError(ErrorCode.EMAIL_ALREADY_EXISTS)
        user = User.objects.create_user(
            email=email, password=data["password"], display_name=data["display_name"]
        )
        payload = auth_token_payload(user, tokens.issue_tokens(user))
        return Response(payload, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.filter(email=data["email"].lower()).first()
        if user is None or not user.check_password(data["password"]):
            raise AppError(ErrorCode.INVALID_CREDENTIALS)
        payload = auth_token_payload(user, tokens.issue_tokens(user))
        return Response(payload, status=status.HTTP_200_OK)


class SocialLoginView(APIView):
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = social.social_login(data["provider"], data["id_token"])
        payload = auth_token_payload(user, tokens.issue_tokens(user))
        return Response(payload, status=status.HTTP_200_OK)


class RefreshView(APIView):
    throttle_classes = [AuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, token_data = tokens.refresh_tokens(
            serializer.validated_data["refresh_token"]
        )
        return Response(auth_token_payload(user, token_data), status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        # Per-session logout (FR-008): revoke only the presented refresh token.
        # Missing / already-revoked / invalid token → idempotent 204 (FR-011),
        # never a 500 or an accidental all-device logout.
        raw_refresh = request.data.get("refresh_token")
        if raw_refresh:
            try:
                tokens.revoke(raw_refresh)
            except AppError:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    def delete(self, request: Request) -> Response:
        request.user.delete()  # cascades to social identities + owned data
        return Response(status=status.HTTP_204_NO_CONTENT)
