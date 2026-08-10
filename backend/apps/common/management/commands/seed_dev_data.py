"""
`python manage.py seed_dev_data`

Creates sample development data (spec section 30) scoped to what this
phase actually builds: default Plans, one sample tenant + business + owner
+ a couple of staff. Later phases (customers, products, conversations, ...)
extend this command as those apps land — see docs/ROADMAP.md.

All data is clearly fictional. Safe to re-run (idempotent by email/slug).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.tenants.models import Plan, Tenant

SAMPLE_BUSINESSES = [
    {
        "tenant_name": "ABC Electronics Ltd",
        "business_name": "ABC Electronics",
        "category": Business.Category.ELECTRONICS,
        "country": "Tanzania",
        "currency": "TZS",
        "owner_email": "owner@abcelectronics.test",
        "owner_first_name": "Amina",
        "owner_last_name": "Juma",
    },
    {
        "tenant_name": "Mambo Fashion House",
        "business_name": "Mambo Fashion",
        "category": Business.Category.FASHION,
        "country": "Kenya",
        "currency": "KES",
        "owner_email": "owner@mambofashion.test",
        "owner_first_name": "David",
        "owner_last_name": "Otieno",
    },
    {
        "tenant_name": "Kijani Foods Co",
        "business_name": "Kijani Foods",
        "category": Business.Category.FOOD_BEVERAGE,
        "country": "Uganda",
        "currency": "UGX",
        "owner_email": "owner@kijanifoods.test",
        "owner_first_name": "Grace",
        "owner_last_name": "Namutebi",
    },
]

DEV_PASSWORD = "DevPassword!2026"


class Command(BaseCommand):
    help = "Seed sample plans, tenants, businesses, and users for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        starter, _ = Plan.objects.get_or_create(
            slug="starter",
            defaults=dict(
                name="Starter",
                price_monthly=0,
                is_default=True,
                max_users=5,
                max_whatsapp_accounts=1,
                max_ai_messages_per_month=1000,
                max_customers=1000,
                max_campaigns_per_month=10,
                max_storage_mb=1024,
            ),
        )
        Plan.objects.get_or_create(
            slug="growth",
            defaults=dict(
                name="Growth",
                price_monthly=49,
                sort_order=1,
                max_users=20,
                max_whatsapp_accounts=3,
                max_ai_messages_per_month=10000,
                max_customers=10000,
                max_campaigns_per_month=50,
                max_storage_mb=10240,
            ),
        )
        self.stdout.write(self.style.SUCCESS("Plans ready: Starter (default), Growth."))

        for spec in SAMPLE_BUSINESSES:
            if User.objects.filter(email__iexact=spec["owner_email"]).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"{spec['business_name']}: owner already exists — skipping."
                    )
                )
                continue

            tenant = Tenant.objects.create(
                name=spec["tenant_name"],
                plan=starter,
                status=Tenant.Status.ACTIVE,
            )
            Business.objects.create(
                tenant=tenant,
                name=spec["business_name"],
                category=spec["category"],
                country=spec["country"],
                currency=spec["currency"],
            )
            User.objects.create_user(
                email=spec["owner_email"],
                password=DEV_PASSWORD,
                first_name=spec["owner_first_name"],
                last_name=spec["owner_last_name"],
                role=User.Role.BUSINESS_OWNER,
                tenant=tenant,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {spec['business_name']} (tenant={tenant.slug}, "
                    f"owner={spec['owner_email']} / {DEV_PASSWORD})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\nSeed complete. All sample owner accounts use the password: " f"{DEV_PASSWORD}"
            )
        )
