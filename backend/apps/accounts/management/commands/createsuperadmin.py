"""
`python manage.py createsuperadmin`

Idempotently creates the platform SUPER_ADMIN from SUPERADMIN_EMAIL /
SUPERADMIN_PASSWORD in .env — the account you log into the Super Admin
dashboard with. Safe to run repeatedly (no-ops if the user already exists
— except MFA enrollment, backfilled on every run; see docs/mfa.md).
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts import mfa
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the platform super admin user from SUPERADMIN_* env vars."

    def handle(self, *args, **options):
        email = getattr(settings, "SUPERADMIN_EMAIL", None) or "admin@wabaai.local"
        password = getattr(settings, "SUPERADMIN_PASSWORD", None)
        first_name = getattr(settings, "SUPERADMIN_FIRST_NAME", "Platform")

        if not password:
            self.stderr.write(
                self.style.ERROR("SUPERADMIN_PASSWORD is not set in your .env - aborting.")
            )
            return

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=first_name,
                last_name="Admin",
            )
            self.stdout.write(self.style.SUCCESS(f"Super admin created: {email}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"Super admin '{email}' already exists - skipping creation.")
            )

        # MFA is required for every role, no exceptions — including this
        # account. Without this, the super admin literally cannot log in
        # (see LoginSerializer) after this command finishes.
        if not user.mfa_enabled:
            secret = mfa.generate_secret()
            user.mfa_secret = secret
            user.mfa_enabled = True
            user.save(update_fields=["mfa_secret_encrypted", "mfa_enabled"])
            backup_codes = mfa.generate_backup_codes()
            mfa.store_backup_codes(user, backup_codes)

            self.stdout.write(self.style.WARNING(f"MFA enrolled for {email} — set this up once:"))
            self.stdout.write(f"  Secret (manual entry): {secret}")
            self.stdout.write(f"  Provisioning URI (QR): {mfa.provisioning_uri(user, secret)}")
            self.stdout.write(f"  Backup codes: {', '.join(backup_codes)}")
