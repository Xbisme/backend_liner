from django.urls import path

from apps.accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RegisterView,
    SocialLoginView,
)

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/social-login", SocialLoginView.as_view(), name="auth-social-login"),
    path("auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("me", MeView.as_view(), name="me"),
]
