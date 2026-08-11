"""
`python manage.py provision_e2e_user`

Dev/test-only: creates (or resets) one fixed, deterministic Business Owner
account — dedicated tenant + business — with MFA already enrolled against a
KNOWN TOTP secret, so Playwright's global setup can drive the *real*
login -> MFA-verify UI flow end-to-end without a human ever typing a code.

The email/password/secret here are fixed, non-production, and MUST match
frontend/e2e/testUser.ts exactly — see that file's own comment. This is the
same "documented dev-only credential" pattern this project already uses for
SUPERADMIN_EMAIL/PASSWORD (see README's "Default development credentials"),
not a real secret.

Idempotent: safe to re-run — resets the password and MFA secret to the
known values every time, so a test run that changed either doesn't strand
future runs.
"""

import pyotp
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts import mfa
from apps.businesses.models import Business
from apps.tenants.models import Plan, Tenant

User = get_user_model()

# Keep these three in sync with frontend/e2e/testUser.ts.
E2E_EMAIL = "e2e-test@wabaai.local"
E2E_PASSWORD = "E2ETestPassword!2026"  # nosec B105 - dev/test-only fixed credential, not a real secret
E2E_TOTP_SECRET = "DPBG3PLCUTAXEA6KLNWPJP3QY4VFS3QF"  # nosec B105 - same as above
E2E_TENANT_NAME = "E2E Test Co"


class Command(BaseCommand):
    help = "Provision (or reset) the fixed E2E test user Playwright logs in as."

    @transaction.atomic
    def handle(self, *args, **options):
        plan = Plan.objects.filter(is_default=True, is_active=True).first()

        tenant, _ = Tenant.objects.get_or_create(
            name=E2E_TENANT_NAME, defaults={"plan": plan, "status": Tenant.Status.ACTIVE}
        )
        if tenant.status != Tenant.Status.ACTIVE:
            tenant.status = Tenant.Status.ACTIVE
            tenant.save(update_fields=["status", "updated_at"])

        Business.objects.get_or_create(
            tenant=tenant,
            defaults={
                "name": E2E_TENANT_NAME,
                "category": "other",
                "country": "KE",
                "currency": "KES",
            },
        )

        user, created = User.objects.get_or_create(
            email=E2E_EMAIL,
            defaults={
                "first_name": "E2E",
                "last_name": "Test",
                "role": User.Role.BUSINESS_OWNER,
                "tenant": tenant,
            },
        )
        user.tenant = tenant
        user.role = User.Role.BUSINESS_OWNER
        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None
        user.set_password(E2E_PASSWORD)
        user.mfa_enabled = True
        user.mfa_secret = E2E_TOTP_SECRET  # property setter — encrypts at rest
        user.save()
        user.mfa_backup_codes.all().delete()

        # Sanity-check the secret actually verifies before declaring success
        # — a typo here would otherwise only surface as a mysterious
        # Playwright failure much later.
        code = pyotp.TOTP(E2E_TOTP_SECRET).now()
        assert mfa.verify_totp(E2E_TOTP_SECRET, code), "TOTP self-check failed — secret mismatch."

        verb = "Created" if created else "Reset"
        self.stdout.write(self.style.SUCCESS(f"{verb} E2E test user {user.email} (tenant: {tenant.name})."))
