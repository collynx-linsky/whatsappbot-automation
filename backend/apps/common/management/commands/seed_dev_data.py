"""
`python manage.py seed_dev_data`

Creates sample development data (spec section 30) scoped to what this
phase actually builds: default Plans, sample tenants + businesses + owners,
a Manager/Staff account for two of the three businesses, a couple of
sample customers per business plus one seeded conversation with messages,
a small product catalog per business, one confirmed sample order tying
a seeded conversation to real product data, and default AI settings
(hybrid mode, human handoff on) per business. Later phases (campaigns,
knowledge base, ...) extend this command as those apps land — see
docs/ROADMAP.md.

All data is clearly fictional. Safe to re-run (idempotent by email/slug).
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.ai.models import AISettings
from apps.businesses.models import Business
from apps.conversations.models import Conversation
from apps.customers.models import Customer
from apps.messages.models import Message
from apps.orders.models import Order, OrderItem
from apps.products.models import Product
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
        "staff": [
            {
                "email": "staff@abcelectronics.test",
                "first_name": "Baraka",
                "last_name": "Mnyonge",
                "role": User.Role.STAFF,
            },
        ],
        "customers": [
            {
                "name": "John Mushi",
                "phone": "+255700111001",
                "status": Customer.Status.QUALIFIED,
                "opening_message": "Hi, do you sell Samsung 55 inch TVs?",
            },
            {"name": "Fatuma Ally", "phone": "+255700111002", "status": Customer.Status.NEW},
        ],
        "products": [
            {
                "name": "Samsung 55in 4K TV",
                "sku": "SAM-TV-55",
                "price": Decimal("850000.00"),
                "stock": 8,
            },
            {
                "name": "LG 43in Smart TV",
                "sku": "LG-TV-43",
                "price": Decimal("520000.00"),
                "stock": 12,
            },
            {"name": "iPhone 15", "sku": "APL-IP15", "price": Decimal("2100000.00"), "stock": 3},
        ],
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
        "staff": [
            {
                "email": "manager@mambofashion.test",
                "first_name": "Wanjiku",
                "last_name": "Mwangi",
                "role": User.Role.MANAGER,
            },
        ],
        "customers": [
            {
                "name": "Grace Wanjiru",
                "phone": "+254700222001",
                "status": Customer.Status.CONTACTED,
                "opening_message": "Is the red Ankara dress still available in size M?",
            },
            {"name": "Peter Kamau", "phone": "+254700222002", "status": Customer.Status.NEW},
        ],
        "products": [
            {
                "name": "Ankara Dress (Red, M)",
                "sku": "ANK-DRS-M-RED",
                "price": Decimal("4500.00"),
                "stock": 6,
            },
            {
                "name": "Kitenge Shirt (L)",
                "sku": "KIT-SHT-L",
                "price": Decimal("2800.00"),
                "stock": 15,
            },
        ],
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
        "customers": [
            {
                "name": "Moses Okello",
                "phone": "+256700333001",
                "status": Customer.Status.NEW,
                "opening_message": "Good morning, what's on today's menu?",
            },
            {"name": "Betty Nakato", "phone": "+256700333002", "status": Customer.Status.NEW},
        ],
        "products": [
            {"name": "Matoke Platter", "sku": "", "price": Decimal("15000.00"), "stock": 40},
            {"name": "Grilled Tilapia", "sku": "", "price": Decimal("28000.00"), "stock": 20},
        ],
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
            existing_owner = User.objects.filter(email__iexact=spec["owner_email"]).first()
            if existing_owner is not None:
                # Re-run on an already-seeded dev DB: don't recreate the
                # tenant/business/owner, but still backfill anything a
                # later phase added since the first run (e.g. AI settings)
                # so this command stays genuinely idempotent, not just
                # idempotent-by-accident on the very first phase it seeded.
                business = Business.objects.filter(tenant=existing_owner.tenant).first()
                if business is not None:
                    self._seed_ai_settings(existing_owner.tenant, business)
                self.stdout.write(
                    self.style.WARNING(
                        f"{spec['business_name']}: owner already exists - skipping creation, "
                        "backfilled AI settings."
                    )
                )
                continue

            tenant = Tenant.objects.create(
                name=spec["tenant_name"],
                plan=starter,
                status=Tenant.Status.ACTIVE,
            )
            business = Business.objects.create(
                tenant=tenant,
                name=spec["business_name"],
                category=spec["category"],
                country=spec["country"],
                currency=spec["currency"],
            )
            owner = User.objects.create_user(
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
            self._seed_staff(tenant, spec.get("staff", []))
            self._seed_ai_settings(tenant, business)
            products = self._seed_products(tenant, spec.get("products", []))
            customer, conversation = self._seed_customers_and_conversation(
                tenant, owner, spec.get("customers", [])
            )
            if customer and products:
                self._seed_sample_order(tenant, owner, customer, conversation, products[0])

        self._report_totals()

        self.stdout.write(
            self.style.SUCCESS(
                "\nSeed complete. All sample owner accounts use the password: " f"{DEV_PASSWORD}"
            )
        )

    def _seed_staff(self, tenant, staff_specs):
        """Sample Manager/Staff accounts, demonstrating the staff-management API's seed data."""
        for s_spec in staff_specs:
            if User.objects.filter(email__iexact=s_spec["email"]).exists():
                continue
            User.objects.create_user(
                email=s_spec["email"],
                password=DEV_PASSWORD,
                first_name=s_spec["first_name"],
                last_name=s_spec.get("last_name", ""),
                role=s_spec["role"],
                tenant=tenant,
            )
            self.stdout.write(
                self.style.SUCCESS(f"  + {s_spec['role']}: {s_spec['email']} / {DEV_PASSWORD}")
            )

    def _seed_ai_settings(self, tenant, business):
        """
        Default AI configuration per business — hybrid mode, human handoff
        on, the built-in keyword list from AISettings.DEFAULT_HANDOFF_KEYWORDS
        (spec section 11's example set). No provider API key is required to
        create these; the actual provider stays unreachable until
        OPENAI_API_KEY/ANTHROPIC_API_KEY is set in .env — generate_ai_reply()
        gracefully hands off to a human in the meantime.
        """
        AISettings.objects.get_or_create(
            business=business,
            defaults={
                "tenant": tenant,
                "assistant_name": f"{business.name} Assistant",
                "welcome_message": (f"Hi! Welcome to {business.name}. How can I help you today?"),
                "handoff_keywords": AISettings.DEFAULT_HANDOFF_KEYWORDS,
            },
        )
        self.stdout.write(self.style.SUCCESS("  + AI settings (hybrid mode, handoff enabled)"))

    def _seed_products(self, tenant, product_specs):
        """Sample catalog entries — enough variety to seed a sample order per business."""
        products = []
        for p_spec in product_specs:
            product, _ = Product.objects.get_or_create(
                tenant=tenant,
                name=p_spec["name"],
                defaults={
                    "sku": p_spec.get("sku", ""),
                    "price": p_spec["price"],
                    "currency": (
                        tenant.businesses.first().currency if tenant.businesses.exists() else "KES"
                    ),
                    "stock": p_spec.get("stock", 0),
                },
            )
            products.append(product)
        if products:
            self.stdout.write(self.style.SUCCESS(f"  + {len(products)} products"))
        return products

    def _seed_sample_order(self, tenant, owner, customer, conversation, product):
        """One CONFIRMED order per business, tying the seeded conversation to real product data."""
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            conversation=conversation,
            currency=product.currency,
            status=Order.Status.PENDING,
        )
        OrderItem.objects.create(
            tenant=tenant,
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=1,
        )
        order.recalculate_total()
        order.status = Order.Status.CONFIRMED
        order.confirmed_by = owner
        order.confirmed_at = timezone.now()
        order.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        self.stdout.write(
            self.style.SUCCESS(f"  + sample order: {product.name} for {customer.name} (confirmed)")
        )

    def _seed_customers_and_conversation(self, tenant, owner, customer_specs):
        """
        Creates sample Customers, and for the first one that has an
        `opening_message`, an OPEN Conversation assigned to the owner with
        an inbound customer message + an outbound staff reply — a stand-in
        for what Phase 7's real WhatsApp webhook will populate. Returns
        (customer, conversation) for that first one, or (None, None).
        """
        first_conversation_created = False
        result = (None, None)
        for c_spec in customer_specs:
            customer, created = Customer.objects.get_or_create(
                tenant=tenant,
                phone=c_spec["phone"],
                defaults={
                    "name": c_spec["name"],
                    "status": c_spec["status"],
                    "source": Customer.Source.WHATSAPP,
                },
            )
            if not created or first_conversation_created or "opening_message" not in c_spec:
                continue

            conversation = Conversation.objects.create(
                tenant=tenant,
                customer=customer,
                assigned_to=owner,
            )
            inbound = Message.objects.create(
                tenant=tenant,
                conversation=conversation,
                sender_type=Message.SenderType.CUSTOMER,
                direction=Message.Direction.INBOUND,
                content=c_spec["opening_message"],
            )
            conversation.record_message(inbound)

            reply = Message.objects.create(
                tenant=tenant,
                conversation=conversation,
                sender_type=Message.SenderType.STAFF,
                sender_user=owner,
                direction=Message.Direction.OUTBOUND,
                content="Thanks for reaching out! Let me check that for you.",
            )
            conversation.record_message(reply)
            customer.touch_interaction()

            first_conversation_created = True
            result = (customer, conversation)

        return result

    def _report_totals(self):
        self.stdout.write(
            self.style.SUCCESS(
                f"Totals: {Tenant.objects.count()} tenants, {Business.objects.count()} businesses, "
                f"{User.objects.count()} users, {Customer.objects.count()} customers, "
                f"{Conversation.objects.count()} conversations, {Message.objects.count()} messages, "
                f"{Product.objects.count()} products, {Order.objects.count()} orders, "
                f"{AISettings.objects.count()} AI settings."
            )
        )
