"""
WhatsAppBusinessAI — Billing Models (spec sections 24, 25)

No separate `Subscription` model: `tenants.Tenant` already carries `plan`
(FK), `status` (`trial|active|suspended|cancelled`), `trial_ends_at`, and
`subscription_ends_at` — everything a `Subscription` model would add is
already there, and duplicating it risks two disagreeing sources of truth
(a `Tenant.status="active"` next to a hypothetical `Subscription.status=
"past_due"`, say). See `docs/billing.md`.

    UsageRecord   how much of a period-scoped Plan limit a tenant has
                  used this calendar month (max_ai_messages_per_month,
                  max_campaigns_per_month — the two limits that reset
                  monthly, unlike max_users/max_customers/
                  max_whatsapp_accounts which are live counts, not
                  usage that accumulates over a period)
    Invoice       a billing-period snapshot record. No payment gateway
                  integration this session (no real credentials, same
                  constraint as OpenAI/Anthropic/Meta all session) — see
                  docs/billing.md for what "generating an invoice" means
                  here vs. what it doesn't (no real charge happens).
"""

from django.db import models

from core.models import BaseModel


class UsageRecord(BaseModel):
    class Metric(models.TextChoices):
        AI_MESSAGES = "ai_messages", "AI messages sent"
        CAMPAIGN_SENDS = "campaign_sends", "Campaigns sent"

    metric = models.CharField(max_length=20, choices=Metric.choices)
    period = models.DateField(
        help_text="First day of the calendar month this usage counts toward."
    )
    count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_usage_record"
        ordering = ["-period"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "metric", "period"], name="unique_usage_record_per_period"
            )
        ]
        indexes = [models.Index(fields=["tenant", "metric", "period"])]

    def __str__(self):
        return f"{self.tenant_id} {self.metric} {self.period:%Y-%m}: {self.count}"


class Invoice(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    invoice_number = models.CharField(max_length=50, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()

    # Snapshotted, not a live FK to Plan — a later plan rename/price
    # change must never retroactively rewrite a historical invoice
    # (same reasoning as OrderItem.product_name/unit_price).
    plan_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    issued_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "billing_invoice"
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period_start"], name="unique_invoice_per_tenant_period"
            )
        ]
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"{self.invoice_number} ({self.get_status_display()})"
