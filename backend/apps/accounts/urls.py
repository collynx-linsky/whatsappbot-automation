"""WhatsAppBusinessAI — Accounts URLs (/api/v1/auth/)"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset-password"),
    path("mfa/setup/", views.MFASetupView.as_view(), name="mfa-setup"),
    path("mfa/setup/confirm/", views.MFASetupConfirmView.as_view(), name="mfa-setup-confirm"),
    path("mfa/verify/", views.MFAVerifyView.as_view(), name="mfa-verify"),
    path("sessions/", views.SessionListView.as_view(), name="session-list"),
    path("sessions/<str:jti>/revoke/", views.SessionRevokeView.as_view(), name="session-revoke"),
]
