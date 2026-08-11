"""
WhatsAppBusinessAI — MFA (TOTP) Service Layer

MFA is required for every role, no exceptions (a deliberate, explicit
platform decision — see docs/mfa.md). This module is the whole TOTP
surface: secret/QR-provisioning-URI generation, code verification, backup
codes, and minting the short-lived "purpose" tokens the two-step login
flow (apps.accounts.serializers.LoginSerializer) hands back instead of
real access/refresh tokens until MFA is actually satisfied.
"""

import hashlib
import secrets
from datetime import timedelta

import pyotp
from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

MFA_SETUP_TOKEN_LIFETIME = timedelta(minutes=10)
MFA_CHALLENGE_TOKEN_LIFETIME = timedelta(minutes=10)
BACKUP_CODE_COUNT = 10


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(user, secret: str) -> str:
    """The otpauth:// URI an authenticator app scans as a QR code. Rendering the
    actual QR image is left to the frontend (e.g. qrcode.react) — see docs/mfa.md."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name=settings.PLATFORM_NAME
    )


def verify_totp(secret: str, code: str) -> bool:
    """`valid_window=1` tolerates the code from one 30s step before/after
    now, for realistic clock drift between the server and the user's phone."""
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except (TypeError, ValueError):
        return False


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def _hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.strip().lower().encode()).hexdigest()


def store_backup_codes(user, codes: list[str]) -> None:
    from .models import MFABackupCode

    user.mfa_backup_codes.all().delete()
    MFABackupCode.objects.bulk_create(
        [MFABackupCode(user=user, code_hash=_hash_backup_code(code)) for code in codes]
    )


def verify_and_consume_backup_code(user, code: str) -> bool:
    """Single-use: a valid code is marked used and cannot be reused, even if resubmitted."""
    from .models import MFABackupCode

    if not code:
        return False
    backup = MFABackupCode.objects.filter(
        user=user, code_hash=_hash_backup_code(code), used_at__isnull=True
    ).first()
    if backup is None:
        return False
    backup.used_at = timezone.now()
    backup.save(update_fields=["used_at"])
    return True


def mint_purpose_token(user, purpose: str, lifetime: timedelta) -> AccessToken:
    """
    A short-lived, narrowly-scoped access token carrying a `purpose` claim
    — accepted only by the specific MFA endpoint matching that purpose
    (core.permissions.IsMFAPending) and refused everywhere else
    (core.authentication.FullAccessJWTAuthentication). Never a substitute
    for the real tokens issued once MFA is actually satisfied.
    """
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=lifetime)
    token["purpose"] = purpose
    return token


def add_standard_claims(token, user):
    """`role`/`tenant_id`/`email` — every *real* token this app issues
    carries these (read by core.middleware.TenantMiddleware and DRF
    permission classes). Shared by LoginSerializer.get_token and
    issue_tokens below so there's one source of truth, not two copies
    that could drift apart."""
    token["role"] = user.role
    token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
    token["email"] = user.email
    return token


def issue_tokens(user) -> dict:
    """
    A real, fully-claimed access+refresh pair — minted only once MFA is
    actually satisfied (setup-confirm or verify). Never called from the
    login endpoint itself; see LoginSerializer.validate.
    """
    refresh = add_standard_claims(RefreshToken.for_user(user), user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
