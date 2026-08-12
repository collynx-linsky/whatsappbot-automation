"""
`python manage.py provision_e2e_user`

Dev/test-only: creates (or resets) two fixed, deterministic accounts — a
Business Owner (dedicated tenant + business) and a platform Super Admin —
each with MFA already enrolled against a KNOWN TOTP secret, so Playwright's
global setup can drive the *real* login -> MFA-verify UI flow end-to-end
without a human ever typing a code. The super admin account exists
specifically so authenticated e2e/visual-QA coverage can reach `/admin`
(the business-owner account correctly cannot — that's the whole point of
`IsSuperAdmin`).

The emails/passwords/secrets here are fixed, non-production, and MUST match
frontend/e2e/testUser.ts exactly — see that file's own comment. This is the
same "documented dev-only credential" pattern this project already uses for
SUPERADMIN_EMAIL/PASSWORD (see README's "Default development credentials"),
not a real secret. Deliberately a *separate* account from the real
SUPERADMIN_EMAIL one `createsuperadmin` manages — this command must never
touch that real seeded identity.

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

# Keep these in sync with frontend/e2e/testUser.ts.
E2E_EMAIL = "e2e-test@wabaai.local"
E2E_PASSWORD = "E2ETestPassword!2026"  # nosec B105 - dev/test-only fixed credential, not a real secret
E2E_TOTP_SECRET = "DPBG3PLCUTAXEA6KLNWPJP3QY4VFS3QF"  # nosec B105 - same as above
E2E_TENANT_NAME = "E2E Test Co"

E2E_ADMIN_EMAIL = "e2e-admin@wabaai.local"
E2E_ADMIN_PASSWORD = "E2EAdminPassword!2026"  # nosec B105 - dev/test-only fixed credential, not a real secret
E2E_ADMIN_TOTP_SECRET = "JJLFDUPIC5LS3D3MAJPCWEQKEMBS3FEF"  # nosec B105 - same as above


class Command(BaseCommand):
    help = "Provision (or reset) the fixed E2E test users Playwright logs in as."

    @transaction.atomic
    def handle(self, *args, **options):
        self._provision_business_owner()
        self._provision_super_admin()

    def _provision_business_owner(self):
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
        self._finish_provisioning(user, E2E_PASSWORD, E2E_TOTP_SECRET)

        verb = "Created" if created else "Reset"
        self.stdout.write(self.style.SUCCESS(f"{verb} E2E business owner {user.email} (tenant: {tenant.name})."))

    def _provision_super_admin(self):
        user, created = User.objects.get_or_create(
            email=E2E_ADMIN_EMAIL,
            defaults={
                "first_name": "E2E",
                "last_name": "Admin",
                "role": User.Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.tenant = None
        user.role = User.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_superuser = True
        self._finish_provisioning(user, E2E_ADMIN_PASSWORD, E2E_ADMIN_TOTP_SECRET)

        verb = "Created" if created else "Reset"
        self.stdout.write(self.style.SUCCESS(f"{verb} E2E super admin {user.email}."))

    def _finish_provisioning(self, user, password: str, totp_secret: str):
        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None
        user.set_password(password)
        user.mfa_enabled = True
        user.mfa_secret = totp_secret  # property setter — encrypts at rest
        user.save()
        user.mfa_backup_codes.all().delete()

        # Sanity-check the secret actually verifies before declaring success
        # — a typo here would otherwise only surface as a mysterious
        # Playwright failure much later.
        code = pyotp.TOTP(totp_secret).now()
        assert mfa.verify_totp(totp_secret, code), "TOTP self-check failed — secret mismatch."
