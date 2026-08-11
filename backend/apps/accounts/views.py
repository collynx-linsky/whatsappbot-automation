"""WhatsAppBusinessAI — Accounts Views (Auth + Staff Management)"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.models import AuditLog
from core.permissions import IsBusinessOwner, IsMFAPending, IsStaffOrAbove

from . import mfa
from .models import PasswordResetToken
from .serializers import (
    CreateStaffSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    MFASetupConfirmSerializer,
    MFAVerifySerializer,
    ResetPasswordSerializer,
    StaffSerializer,
    UpdateStaffSerializer,
    UserSerializer,
)

User = get_user_model()

RESET_TOKEN_TTL = timedelta(hours=1)


class LoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/ — email + password. Never returns real
    tokens directly (MFA is required for every role — see docs/mfa.md);
    returns `{mfa_setup_required, setup_token}` or `{mfa_required,
    challenge_token}` instead. See LoginSerializer.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"


class MFASetupView(APIView):
    """
    POST /api/v1/auth/mfa/setup/ — first login only (`setup_token` from
    `LoginView`). Generates a fresh TOTP secret and returns it plus a
    provisioning URI for the frontend to render as a QR code (this API
    doesn't render images — see docs/mfa.md). Calling this again before
    confirming discards the previous unconfirmed secret; harmless, since
    nothing was ever enrolled with it.
    """

    authentication_classes = [JWTAuthentication]  # accepts the purpose-tagged setup token
    permission_classes = [IsMFAPending]
    mfa_purpose = "mfa_setup"

    def post(self, request):
        user = request.user
        secret = mfa.generate_secret()
        user.mfa_secret = secret
        user.save(update_fields=["mfa_secret_encrypted"])
        return Response({"secret": secret, "provisioning_uri": mfa.provisioning_uri(user, secret)})


class MFASetupConfirmView(APIView):
    """
    POST /api/v1/auth/mfa/setup/confirm/ {"code": "123456"} — completes
    enrollment. On success: `mfa_enabled=True`, 10 backup codes generated
    and returned **once** (plaintext — only the hash is ever stored; see
    apps.accounts.mfa.store_backup_codes), and real access/refresh tokens
    issued — this is the only way a first-time user actually gets in.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsMFAPending]
    mfa_purpose = "mfa_setup"
    throttle_scope = "mfa_verify"

    def post(self, request):
        user = request.user
        serializer = MFASetupConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not user.mfa_secret:
            raise ValidationError("Call /api/v1/auth/mfa/setup/ first to generate a secret.")
        if not mfa.verify_totp(user.mfa_secret, serializer.validated_data["code"]):
            user.increment_failed_login()
            raise ValidationError("Incorrect code.")

        user.reset_failed_login()
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])

        backup_codes = mfa.generate_backup_codes()
        mfa.store_backup_codes(user, backup_codes)

        AuditLog.log(
            action="MFA_ENABLED",
            user=user,
            tenant=user.tenant,
            obj=user,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({**mfa.issue_tokens(user), "backup_codes": backup_codes})


class MFAVerifyView(APIView):
    """
    POST /api/v1/auth/mfa/verify/ {"code": "123456"} or {"backup_code":
    "ab12cd34-ef56ab78"} — second login step for an already-enrolled user
    (`challenge_token` from `LoginView`). Wrong code/backup code counts
    against the same lockout counter a wrong password does
    (User.increment_failed_login) — brute-forcing a 6-digit TOTP code is a
    real risk without this, paired with tight rate limiting on this
    endpoint (docs/security.md).
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsMFAPending]
    mfa_purpose = "mfa_challenge"
    throttle_scope = "mfa_verify"

    def post(self, request):
        user = request.user
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        valid = (
            mfa.verify_totp(user.mfa_secret, data["code"])
            if data.get("code")
            else mfa.verify_and_consume_backup_code(user, data["backup_code"])
        )
        if not valid:
            user.increment_failed_login()
            raise ValidationError("Incorrect code.")

        user.reset_failed_login()
        user.last_login = timezone.now()
        user.last_login_ip = request.META.get("REMOTE_ADDR")
        user.last_login_user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
        user.save(update_fields=["last_login", "last_login_ip", "last_login_user_agent"])

        return Response(mfa.issue_tokens(user))


class MFAResetView(APIView):
    """
    POST /api/v1/staff/{id}/mfa-reset/ — Business Owner (own tenant) or
    Super Admin (any tenant, for supporting a Business Owner who locked
    themselves out). "Lost the device AND the backup codes" recovery path
    — clears mfa_enabled/secret/backup codes, so the target re-enrolls
    from scratch on their next login. Never self-service beyond that: a
    Business Owner still can't reset another tenant's owner or a super
    admin. See `manage.py reset_mfa` for the platform's own break-glass
    path if a super admin locks themselves out (docs/mfa.md).
    """

    permission_classes = [IsBusinessOwner]

    def post(self, request, pk):
        actor = request.user
        queryset = (
            User.objects.all()
            if actor.is_superuser
            else User.objects.filter(tenant_id=actor.tenant_id)
        )
        target = get_object_or_404(queryset, pk=pk)
        if (
            target.role in (User.Role.BUSINESS_OWNER, User.Role.SUPER_ADMIN)
            and not actor.is_superuser
        ):
            raise ValidationError("Cannot reset the business owner's MFA via this endpoint.")

        target.mfa_enabled = False
        target.mfa_secret_encrypted = ""
        target.save(update_fields=["mfa_enabled", "mfa_secret_encrypted"])
        target.mfa_backup_codes.all().delete()

        AuditLog.log(
            action="MFA_RESET",
            user=actor,
            tenant=target.tenant,
            obj=target,
            metadata={"target_email": target.email},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response({"detail": "MFA has been reset. This user must re-enroll on next login."})


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


class StaffListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/staff/ — team roster (owner + manager + staff) for the
    caller's own tenant. Any staff+ role can view it.
    POST /api/v1/staff/ — Business Owner only: add a Manager or Staff
    account. Generates a temporary password (spec's onboarding pattern),
    emails it, and returns it once — never accepted as client input.
    """

    serializer_class = StaffSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsBusinessOwner()]
        return [IsStaffOrAbove()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.exclude(tenant__isnull=True).order_by("first_name", "last_name")
        return User.objects.filter(tenant_id=user.tenant_id).order_by("first_name", "last_name")

    def create(self, request, *args, **kwargs):
        if request.user.tenant is None:
            # A super admin has no tenant of their own — adding staff "to"
            # nothing isn't a meaningful action here (same guard as
            # core.mixins.TenantScopedCreateMixin, reimplemented because
            # this view builds the User directly rather than via a
            # serializer.save(tenant=...) call).
            raise ValidationError(
                "A super admin has no tenant of their own and cannot add staff directly."
            )

        from apps.billing.services import check_limit

        check_limit(request.user.tenant, "users")

        serializer = CreateStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        temporary_password = secrets.token_urlsafe(12)
        new_user = User.objects.create_user(
            email=data["email"],
            password=temporary_password,
            first_name=data["first_name"],
            last_name=data.get("last_name", ""),
            phone=data.get("phone", ""),
            role=data["role"],
            tenant=request.user.tenant,
        )

        AuditLog.log(
            action="STAFF_ADDED",
            user=request.user,
            tenant=request.user.tenant,
            obj=new_user,
            metadata={"role": new_user.role, "email": new_user.email},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        send_mail(
            subject=f"You've been added to {settings.PLATFORM_NAME}",
            message=(
                f"You've been added as {new_user.get_role_display()} on "
                f"{request.user.tenant.name}'s {settings.PLATFORM_NAME} account.\n\n"
                f"Login: {new_user.email}\n"
                f"Temporary password: {temporary_password}\n\n"
                f"Sign in at {settings.FRONTEND_URL}/login and change your password."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[new_user.email],
            fail_silently=True,
        )

        return Response(
            {"user": StaffSerializer(new_user).data, "temporary_password": temporary_password},
            status=status.HTTP_201_CREATED,
        )


class StaffDetailView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/staff/{id}/ — staff+.
    PATCH /api/v1/staff/{id}/ — Business Owner only. Cannot target the
    business owner themself (no self-service role changes / lockout via
    this endpoint) or the caller's own account.
    """

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAbove()]
        return [IsBusinessOwner()]

    def get_serializer_class(self):
        return UpdateStaffSerializer if self.request.method == "PATCH" else StaffSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.exclude(tenant__isnull=True)
        return User.objects.filter(tenant_id=user.tenant_id)

    def perform_update(self, serializer):
        target = serializer.instance
        if target.role in (User.Role.BUSINESS_OWNER, User.Role.SUPER_ADMIN):
            raise ValidationError("Cannot modify the business owner via this endpoint.")
        if target.id == self.request.user.id:
            raise ValidationError("Cannot modify your own account via this endpoint.")

        updated_user = serializer.save()
        AuditLog.log(
            action="STAFF_UPDATED",
            user=self.request.user,
            # The target's tenant, not the actor's — matters when a super
            # admin (tenant=None) is the one making the change.
            tenant=updated_user.tenant,
            obj=updated_user,
            metadata={"role": updated_user.role, "is_active": updated_user.is_active},
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
