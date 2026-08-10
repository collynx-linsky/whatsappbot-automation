"""WhatsAppBusinessAI — Accounts Views (Auth)"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import PasswordResetToken
from .serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)

User = get_user_model()

RESET_TOKEN_TTL = timedelta(hours=1)


class LoginView(TokenObtainPairView):
    """POST /api/v1/auth/login/ — email + password -> access/refresh tokens."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — blacklists the given refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "`refresh` token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or already-expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """GET /api/v1/auth/me/ — the authenticated user's own profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ForgotPasswordView(APIView):
    """
    POST /api/v1/auth/forgot-password/ {"email": "..."}

    Always returns 200 regardless of whether the email exists, to avoid
    leaking account existence. Sends via EMAIL_BACKEND (console in dev).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            token = secrets.token_urlsafe(32)
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + RESET_TOKEN_TTL,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
            send_mail(
                subject=f"{settings.PLATFORM_NAME} — Password Reset",
                message=(
                    f"A password reset was requested for your account.\n\n"
                    f"Reset link (valid 1 hour): {reset_url}\n\n"
                    f"If you did not request this, you can ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

        return Response({"detail": "If that email exists, a reset link has been sent."})


class ResetPasswordView(APIView):
    """POST /api/v1/auth/reset-password/ {"token": "...", "new_password": "..."}"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_value = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        reset_token = PasswordResetToken.objects.filter(token=token_value).first()
        if not reset_token or not reset_token.is_valid():
            return Response(
                {"detail": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = reset_token.user
        user.set_password(new_password)
        user.reset_failed_login()
        user.save()

        reset_token.used_at = timezone.now()
        reset_token.save(update_fields=["used_at"])

        return Response({"detail": "Password has been reset. You can now log in."})
