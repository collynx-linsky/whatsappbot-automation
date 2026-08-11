"""WhatsAppBusinessAI — Accounts Serializers"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from . import mfa

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "tenant_id",
            "tenant_name",
            "is_active",
            "date_joined",
        ]
        read_only_fields = fields


class LoginSerializer(TokenObtainPairSerializer):
    """
    Email + password only gets as far as MFA — see docs/mfa.md. This
    deliberately never returns a real access/refresh pair; it either
    returns `{mfa_setup_required: True, setup_token}` (first login, no
    TOTP enrolled yet) or `{mfa_required: True, challenge_token}`
    (already enrolled). Real tokens only come from
    `POST /api/v1/auth/mfa/setup/confirm/` or `POST /api/v1/auth/mfa/verify/`.

    `get_token()` below still adds `role`/`tenant_id` claims to every
    *real* JWT this app mints (read by core.middleware.TenantMiddleware
    and DRF permission classes) — but the short-lived purpose tokens
    minted by `apps.accounts.mfa.mint_purpose_token` for the MFA-pending
    stages go through `AccessToken.for_user` directly, not this class, so
    they deliberately carry neither claim: they must only ever reach the
    MFA endpoints themselves (enforced by core.authentication /
    core.permissions.IsMFAPending), which look the user up directly and
    have no need for tenant-scoping claims a permission class elsewhere
    might otherwise trust.

    Also enforces the account-lockout policy (spec section 25 —
    brute-force protection), shared with MFA-code failures — see
    apps.accounts.models.User's lockout fields.
    """

    @classmethod
    def get_token(cls, user):
        return mfa.add_standard_claims(super().get_token(user), user)

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        if user and user.is_locked:
            raise serializers.ValidationError(
                "This account is temporarily locked due to repeated failed login "
                "attempts. Please try again later or reset your password."
            )

        try:
            super().validate(attrs)  # password check only — real tokens discarded below
        except Exception:
            if user:
                user.increment_failed_login()
            raise

        user.reset_failed_login()
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        if not user.mfa_enabled:
            token = mfa.mint_purpose_token(user, "mfa_setup", mfa.MFA_SETUP_TOKEN_LIFETIME)
            return {"mfa_setup_required": True, "setup_token": str(token)}

        token = mfa.mint_purpose_token(user, "mfa_challenge", mfa.MFA_CHALLENGE_TOKEN_LIFETIME)
        return {"mfa_required": True, "challenge_token": str(token)}


class MFASetupConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)


class MFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True, max_length=8)
    backup_code = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate(self, attrs):
        if not attrs.get("code") and not attrs.get("backup_code"):
            raise serializers.ValidationError("Provide either `code` or `backup_code`.")
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


class StaffSerializer(serializers.ModelSerializer):
    """Read serializer for a tenant's team roster (owner + manager + staff)."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "date_joined",
        ]
        read_only_fields = fields


class CreateStaffSerializer(serializers.Serializer):
    """
    Business-owner-only: adds a MANAGER or STAFF user to the caller's own
    tenant. Deliberately cannot create BUSINESS_OWNER or SUPER_ADMIN — those
    only come from platform onboarding (apps.tenants.OnboardBusinessSerializer)
    and manage.py createsuperadmin, respectively.
    """

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[User.Role.MANAGER, User.Role.STAFF])

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class UpdateStaffSerializer(serializers.ModelSerializer):
    """
    Business-owner-only: edit an existing MANAGER/STAFF user's profile,
    role, or active status. The view enforces (not this serializer) that
    the target isn't the owner themself or the caller's own account — see
    apps.accounts.views.StaffDetailView.perform_update.
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "role", "is_active"]

    def validate_role(self, value):
        if value not in (User.Role.MANAGER, User.Role.STAFF):
            raise serializers.ValidationError("Role must be 'manager' or 'staff'.")
        return value
