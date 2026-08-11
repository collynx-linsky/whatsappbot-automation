"""
`python manage.py generate_invoices [--period YYYY-MM-DD]`

Generates one Invoice per active/trial tenant for the given billing
period (defaults to the current calendar month). This is the batch
counterpart to `POST /api/v1/billing/invoices/generate/` (which targets
one tenant, e.g. for support) — in a real deployment this would run from
a `celery beat` schedule on the 1st of each month; no such schedule is
wired up this session since there's no real payment gateway to actually
act on the invoices it creates (see docs/billing.md). Idempotent: safe to
re-run for the same period, existing invoices are left untouched.
"""

import datetime

from django.core.management.base import BaseCommand

from apps.billing.services import generate_invoice
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Generate this month's invoice for every active/trial tenant with a Plan assigned."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            type=str,
            default=None,
            help="Billing period as YYYY-MM-DD (any day in the target month). Defaults to today's month.",
        )

    def handle(self, *args, **options):
        if options["period"]:
            period_start = datetime.date.fromisoformat(options["period"]).replace(day=1)
        else:
            period_start = datetime.date.today().replace(day=1)

        next_month = (period_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        period_end = next_month - datetime.timedelta(days=1)

        tenants = Tenant.objects.filter(
            status__in=[Tenant.Status.TRIAL, Tenant.Status.ACTIVE], plan__isnull=False
        )
        created, skipped = 0, 0
        for tenant in tenants:
            from apps.billing.models import Invoice

            already_exists = Invoice.objects.filter(
                tenant=tenant, period_start=period_start
            ).exists()
            invoice = generate_invoice(tenant, period_start, period_end)
            if invoice is None:
                continue
            if already_exists:
                skipped += 1
            else:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + {invoice.invoice_number} — {tenant.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} invoice(s) created, {skipped} already existed for "
                f"{period_start:%B %Y}."
            )
        )
