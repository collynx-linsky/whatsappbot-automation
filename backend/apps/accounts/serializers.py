"""WhatsAppBusinessAI — Accounts Serializers"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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
    Adds `role` and `tenant_id` claims to the issued JWT — read by
    core.middleware.TenantMiddleware and DRF permission classes. Also
    enforces the account-lockout policy (spec section 25 — brute-force
    protection).
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["email"] = user.email
        return token

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
            data = super().validate(attrs)
        except Exception:
            if user:
                user.increment_failed_login()
            raise

        if user:
            user.reset_failed_login()
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

        data["user"] = UserSerializer(self.user).data
        return data


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
