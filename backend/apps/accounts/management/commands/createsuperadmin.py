"""
`python manage.py createsuperadmin`

Idempotently creates the platform SUPER_ADMIN from SUPERADMIN_EMAIL /
SUPERADMIN_PASSWORD in .env — the account you log into the Super Admin
dashboard with. Safe to run repeatedly (no-ops if the user already exists).
"""

from django.conf import settings
from django.core.management.base import BaseCommand

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

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(
                self.style.WARNING(f"Super admin '{email}' already exists - skipping.")
            )
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name="Admin",
        )
        self.stdout.write(self.style.SUCCESS(f"Super admin created: {email}"))
