"""
WhatsAppBusinessAI — Plan Limit Enforcement & Invoicing (spec sections 24, 25)

check_limit() is called from every resource-creating view/service this
phase wires it into (staff invites, WhatsApp account connection, customer
creation, AI replies, campaign sends) — see docs/billing.md for the full
list and why `max_storage_mb` is NOT enforced yet (flagged honestly, not
silently skipped).
"""

import datetime
import logging

from django.db.models import F
from django.utils import timezone

from .exceptions import PlanLimitExceeded
from .models import Invoice, UsageRecord

logger = logging.getLogger("waba")

INVOICE_DUE_DAYS = 14


def _count_users(tenant) -> int:
    from apps.accounts.models import User

    return User.objects.filter(tenant=tenant, is_active=True).count()


def _count_whatsapp_accounts(tenant) -> int:
    from apps.whatsapp.models import WhatsAppAccount

    return WhatsAppAccount.objects.filter(tenant=tenant).count()


def _count_customers(tenant) -> int:
    from apps.customers.models import Customer

    return Customer.objects.filter(tenant=tenant).count()


def current_month_start() -> datetime.date:
    today = timezone.localdate()
    return today.replace(day=1)


def _count_period_usage(metric: str):
    def _count(tenant) -> int:
        record = UsageRecord.objects.filter(
            tenant=tenant, metric=metric, period=current_month_start()
        ).first()
        return record.count if record else 0

    return _count


# Maps a limit name (used at every call site) to the Plan field that caps
# it and how current usage is measured. "users"/"whatsapp_accounts"/
# "customers" are live counts (re-derived from the actual tables every
# check — always correct, no drift possible); "ai_messages"/
# "campaign_sends" are period usage, since those Plan limits are
# explicitly "per month" and a live count of all-time messages/sends
# would never reflect what the plan actually caps.
LIMIT_CHECKS = {
    "users": {"plan_field": "max_users", "counter": _count_users},
    "whatsapp_accounts": {
        "plan_field": "max_whatsapp_accounts",
        "counter": _count_whatsapp_accounts,
    },
    "customers": {"plan_field": "max_customers", "counter": _count_customers},
    "ai_messages": {
        "plan_field": "max_ai_messages_per_month",
        "counter": _count_period_usage(UsageRecord.Metric.AI_MESSAGES),
    },
    "campaign_sends": {
        "plan_field": "max_campaigns_per_month",
        "counter": _count_period_usage(UsageRecord.Metric.CAMPAIGN_SENDS),
    },
}


def check_limit(tenant, limit_name: str) -> None:
    """
    Raises PlanLimitExceeded (402) if `tenant` is already at or over its
    Plan's limit for `limit_name`. A `None` tenant (super admin action) or
    a tenant with no Plan assigned skips the check — there's nothing to
    enforce against. A Plan limit of `0` means unlimited (per
    `tenants.Plan`'s own field help text).
    """
    if tenant is None:
        return
    if tenant.plan is None:
        logger.warning(
            "Tenant %s has no plan assigned — skipping '%s' limit check.", tenant.id, limit_name
        )
        return

    config = LIMIT_CHECKS[limit_name]
    max_allowed = getattr(tenant.plan, config["plan_field"])
    if max_allowed == 0:
        return

    current = config["counter"](tenant)
    if current >= max_allowed:
        label = limit_name.replace("_", " ")
        raise PlanLimitExceeded(
            f"Your plan ({tenant.plan.name}) allows up to {max_allowed} {label}; "
            f"you're currently at {current}. Upgrade your plan to continue."
        )


def is_over_limit(tenant, limit_name: str) -> bool:
    """
    Same check as check_limit(), but returns a bool instead of raising —
    for call sites that aren't a DRF view (e.g. apps.ai's Celery task),
    where the right response to "over limit" is to degrade gracefully
    (hand off to a human) rather than raise an HTTP-flavored exception
    nothing would catch.
    """
    if tenant is None or tenant.plan is None:
        return False
    config = LIMIT_CHECKS[limit_name]
    max_allowed = getattr(tenant.plan, config["plan_field"])
    if max_allowed == 0:
        return False
    return config["counter"](tenant) >= max_allowed


def increment_usage(tenant, metric: str, amount: int = 1) -> None:
    """Adds `amount` to `tenant`'s usage counter for `metric` in the current calendar month."""
    if tenant is None:
        return
    period = current_month_start()
    record, _ = UsageRecord.objects.get_or_create(
        tenant=tenant, metric=metric, period=period, defaults={"count": 0}
    )
    UsageRecord.objects.filter(pk=record.pk).update(count=F("count") + amount)


def usage_summary(tenant) -> dict:
    """Current usage vs. limit for every Plan field this app enforces — the billing dashboard payload."""
    if tenant is None or tenant.plan is None:
        return {"plan": None, "limits": {}}

    limits = {}
    for limit_name, config in LIMIT_CHECKS.items():
        max_allowed = getattr(tenant.plan, config["plan_field"])
        limits[limit_name] = {
            "used": config["counter"](tenant),
            "limit": max_allowed,
            "unlimited": max_allowed == 0,
        }
    return {"plan": tenant.plan.name, "limits": limits}


def generate_invoice(
    tenant, period_start: datetime.date, period_end: datetime.date
) -> Invoice | None:
    """
    Creates (or returns the existing) Invoice for `tenant`'s billing
    period, snapshotting the plan's current name/price. **No real payment
    gateway integration** — this records what's owed; nothing charges a
    card. See docs/billing.md for what's genuinely built vs. not.
    Idempotent per (tenant, period_start) — calling this twice for the
    same month returns the same invoice, never a duplicate.
    """
    if tenant.plan is None:
        logger.warning("Tenant %s has no plan assigned — cannot generate an invoice.", tenant.id)
        return None

    invoice_number = f"INV-{tenant.slug}-{period_start:%Y%m}".upper()
    now = timezone.now()
    invoice, _ = Invoice.objects.get_or_create(
        tenant=tenant,
        period_start=period_start,
        defaults={
            "invoice_number": invoice_number,
            "period_end": period_end,
            "plan_name": tenant.plan.name,
            "amount": tenant.plan.price_monthly,
            "currency": tenant.plan.currency,
            "status": Invoice.Status.ISSUED,
            "issued_at": now,
            "due_at": now + timezone.timedelta(days=INVOICE_DUE_DAYS),
        },
    )
    return invoice
