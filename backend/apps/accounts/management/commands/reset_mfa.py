"""
`python manage.py reset_mfa <email>`

Break-glass MFA recovery, run directly against the server (not via the
API) — for the one case nothing else covers: a Super Admin who loses
their device and backup codes. `POST /api/v1/staff/{id}/mfa-reset/`
requires a Business Owner or an *already-authenticated* Super Admin, so
it can't help a Super Admin who is themselves locked out. This command
requires shell/server access, which is the appropriate bar for resetting
the platform's most privileged account's second factor. See docs/mfa.md.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Reset a user's MFA enrollment (break-glass recovery) — they re-enroll on next login."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)

    def handle(self, *args, **options):
        email = options["email"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise CommandError(f"No user found with email '{email}'.") from exc

        if not user.mfa_enabled and not user.mfa_secret_encrypted:
            self.stdout.write(
                self.style.WARNING(f"{user.email} has no MFA enrolled — nothing to do.")
            )
            return

        user.mfa_enabled = False
        user.mfa_secret_encrypted = ""
        user.save(update_fields=["mfa_enabled", "mfa_secret_encrypted"])
        user.mfa_backup_codes.all().delete()

        self.stdout.write(
            self.style.SUCCESS(f"MFA reset for {user.email}. They must re-enroll on next login.")
        )
