"""
WhatsAppBusinessAI — Accounts Models

Custom User model with 4 fixed platform roles (spec section 6). Users
belong to exactly one tenant, except SUPER_ADMIN which is platform-wide
(tenant=None).
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.crypto import decrypt_secret, encrypt_secret


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.STAFF)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields["role"] = User.Role.SUPER_ADMIN
        extra_fields["tenant"] = None
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model — email login, fixed role, tenant-bound."""

    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        BUSINESS_OWNER = "business_owner", "Business Owner"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        help_text="Null only for SUPER_ADMIN, who is platform-wide.",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF, db_index=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False, help_text="Django admin site access.")

    # Security bookkeeping
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # MFA (TOTP) — required for every role, no exceptions (see docs/mfa.md).
    # `failed_login_attempts`/`locked_until` above are deliberately reused
    # for MFA-code failures too (increment_failed_login is called from the
    # MFA verify endpoint on a wrong code, same as a wrong password) — a
    # single shared lockout counter for "too many wrong authentication
    # attempts of any kind," rather than a second, parallel bookkeeping
    # scheme with its own edge cases.
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.CharField(
        max_length=255, blank=True, help_text="Fernet-encrypted TOTP secret — see core.crypto."
    )
    last_login_user_agent = models.CharField(max_length=255, blank=True)

    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    class Meta:
        db_table = "accounts_user"
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "role"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role="super_admin", tenant__isnull=True)
                | ~models.Q(role="super_admin"),
                name="super_admin_has_no_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return " ".join(filter(None, [self.first_name, self.last_name])) or self.email

    def get_short_name(self):
        return self.first_name or self.email

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def increment_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            from datetime import timedelta

            self.locked_until = timezone.now() + timedelta(minutes=30)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def reset_failed_login(self):
        if self.failed_login_attempts or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=["failed_login_attempts", "locked_until"])

    @property
    def mfa_secret(self) -> str:
        """Decrypted TOTP secret — never serialized, only read by apps.accounts.mfa."""
        return decrypt_secret(self.mfa_secret_encrypted) if self.mfa_secret_encrypted else ""

    @mfa_secret.setter
    def mfa_secret(self, value: str):
        self.mfa_secret_encrypted = encrypt_secret(value) if value else ""


class PasswordResetToken(models.Model):
    """One-time password reset tokens (spec: Forgot/Reset password flow)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "accounts_password_reset_token"

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class MFABackupCode(models.Model):
    """
    One-time MFA recovery codes, generated in a batch of 10 when a user
    confirms TOTP setup (apps.accounts.mfa.generate_backup_codes) — for
    "I have my backup codes but not my authenticator app" recovery,
    without needing an admin to reset MFA entirely. Only the SHA-256 hash
    is stored (single-use random codes, not passwords someone needs to
    remember — a fast hash is the right tool here, not a slow one).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_backup_codes")
    code_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_mfa_backup_code"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "code_hash"], name="unique_backup_code_hash_per_user"
            ),
        ]

    def __str__(self):
        return f"Backup code for {self.user.email} ({'used' if self.used_at else 'unused'})"
