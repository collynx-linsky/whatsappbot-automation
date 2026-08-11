"""
WhatsAppBusinessAI — Platform-Wide Analytics (super admin, spec section 17)

Separate module from services.py because these queries are deliberately
NOT tenant-scoped — every function here reads across every tenant, and
mixing that with the per-tenant helpers in the same file would make it
too easy to accidentally call the wrong one from a tenant-scoped view.
"""

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.conversations.models import Conversation
from apps.messages.models import Message
from apps.orders.models import Order
from apps.tenants.models import Tenant

from .services import REVENUE_STATUSES

SIGNUP_TREND_DAYS = 30


def tenant_counts() -> dict:
    counts = dict(Tenant.objects.values_list("status").annotate(count=Count("id")))
    result = {status: counts.get(status, 0) for status, _ in Tenant.Status.choices}
    result["total"] = sum(result.values())
    return result


def user_counts() -> dict:
    counts = dict(User.objects.values_list("role").annotate(count=Count("id")))
    result = {role: counts.get(role, 0) for role, _ in User.Role.choices}
    result["total"] = sum(result.values())
    return result


def platform_revenue() -> dict:
    """Same currency-grouped honesty as apps.analytics.services.order_revenue, platform-wide."""
    revenue_qs = (
        Order.objects.filter(status__in=REVENUE_STATUSES)
        .values("currency")
        .annotate(total=Sum("total_amount"))
    )
    return {row["currency"]: row["total"] for row in revenue_qs}


def signup_trend(days: int = SIGNUP_TREND_DAYS) -> list[dict]:
    """New tenants per day, most recent `days` days — a simple growth trend, not a forecast."""
    since = timezone.now() - timezone.timedelta(days=days)
    rows = (
        Tenant.objects.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    return [{"date": row["day"].isoformat(), "count": row["count"]} for row in rows]


def platform_dashboard() -> dict:
    return {
        "tenants": tenant_counts(),
        "businesses": {"total": Business.objects.count()},
        "users": user_counts(),
        "conversations": {"total": Conversation.objects.count()},
        "messages": {"total": Message.objects.count()},
        "orders": {"total": Order.objects.count(), "revenue_by_currency": platform_revenue()},
        "signup_trend": signup_trend(),
    }
