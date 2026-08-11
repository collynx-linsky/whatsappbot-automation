"""
WhatsAppBusinessAI — Analytics (spec section 17)

No new persisted models this phase — every number here is computed live
from existing data (Customer/Conversation/Message/Order/Campaign), not a
materialized snapshot. Fine at this project's MVP scale; see
docs/analytics.md for the documented scaling note (a periodic aggregation
job/snapshot table is the natural next step once a tenant's message
volume makes live computation slow).

Scoped by **tenant**, not `Business`, matching every other view in this
codebase — `Conversation`/`Message`/`Order` only carry a `tenant` FK, not
a `business` FK, so true per-business analytics for a tenant with more
than one business isn't representable yet (onboarding currently creates
exactly one business per tenant; see docs/database.md's own note on this).
"""

import re
from collections import Counter

from django.db.models import Count, Sum

from apps.common.models import AuditLog
from apps.conversations.models import Conversation
from apps.customers.models import Customer
from apps.messages.models import Message
from apps.orders.models import Order

REVENUE_STATUSES = [
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.READY,
    Order.Status.DELIVERED,
]
TOP_QUESTIONS_LIMIT = 10
_WHITESPACE = re.compile(r"\s+")


def _date_bounded(qs, field, start, end):
    if start:
        qs = qs.filter(**{f"{field}__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__lte": end})
    return qs


def customer_funnel(tenant, start=None, end=None) -> dict:
    """Counts customers per lead-pipeline stage (spec section 17's funnel)."""
    qs = _date_bounded(Customer.objects.filter(tenant=tenant), "created_at", start, end)
    counts = dict(qs.values_list("status").annotate(count=Count("id")))
    return {status: counts.get(status, 0) for status, _ in Customer.Status.choices}


def conversation_counts(tenant, start=None, end=None) -> dict:
    qs = _date_bounded(Conversation.objects.filter(tenant=tenant), "created_at", start, end)
    counts = dict(qs.values_list("status").annotate(count=Count("id")))
    result = {status: counts.get(status, 0) for status, _ in Conversation.Status.choices}
    result["total"] = sum(result.values())
    return result


def message_counts(tenant, start=None, end=None) -> dict:
    qs = _date_bounded(Message.objects.filter(tenant=tenant), "created_at", start, end)
    by_sender = dict(qs.values_list("sender_type").annotate(count=Count("id")))
    return {
        "total": sum(by_sender.values()),
        "by_sender_type": {
            sender_type: by_sender.get(sender_type, 0)
            for sender_type, _ in Message.SenderType.choices
        },
    }


def order_revenue(tenant, start=None, end=None) -> dict:
    """
    Revenue from orders past the confirmation point (spec section 14 — a
    PENDING order isn't real revenue yet, and a CANCELLED one never was).
    Grouped by currency rather than summed into one number — a tenant's
    orders are not guaranteed to share a currency (see docs/database.md),
    and silently summing TZS and KES together would be a real lie, not
    just an approximation.
    """
    qs = _date_bounded(Order.objects.filter(tenant=tenant), "created_at", start, end)
    by_status = dict(qs.values_list("status").annotate(count=Count("id")))
    revenue_qs = (
        qs.filter(status__in=REVENUE_STATUSES)
        .values("currency")
        .annotate(total=Sum("total_amount"))
    )
    revenue_by_currency = {row["currency"]: row["total"] for row in revenue_qs}
    return {
        "by_status": {status: by_status.get(status, 0) for status, _ in Order.Status.choices},
        "revenue_by_currency": revenue_by_currency,
    }


def ai_performance(tenant, start=None, end=None) -> dict:
    """AI-authored replies vs. handoffs to a human, from real Message/AuditLog data."""
    messages = _date_bounded(Message.objects.filter(tenant=tenant), "created_at", start, end)
    ai_replies = messages.filter(sender_type=Message.SenderType.AI).count()
    handoffs = _date_bounded(
        AuditLog.objects.filter(tenant=tenant, action="AI_HANDOFF"), "created_at", start, end
    ).count()
    return {"ai_replies_sent": ai_replies, "handoffs": handoffs}


def average_response_time(tenant, start=None, end=None) -> dict:
    """
    For every run of consecutive inbound customer messages, measures the
    time until the next outbound (staff/AI/campaign) message in that same
    conversation, and averages across every such gap in the period.
    Single ordered pass over the tenant's messages — O(n), no N+1 queries.
    """
    qs = _date_bounded(Message.objects.filter(tenant=tenant), "created_at", start, end)
    rows = qs.order_by("conversation_id", "created_at").values_list(
        "conversation_id", "direction", "created_at"
    )

    pending_since = {}
    samples = []
    for conversation_id, direction, created_at in rows:
        if direction == Message.Direction.INBOUND:
            pending_since.setdefault(conversation_id, created_at)
        else:
            first_unanswered = pending_since.pop(conversation_id, None)
            if first_unanswered is not None:
                samples.append((created_at - first_unanswered).total_seconds())

    if not samples:
        return {"average_seconds": None, "sample_count": 0}
    return {"average_seconds": round(sum(samples) / len(samples), 1), "sample_count": len(samples)}


def top_customer_questions(tenant, start=None, end=None, limit=TOP_QUESTIONS_LIMIT) -> list[dict]:
    """
    The most-repeated inbound customer messages, normalized (trimmed,
    collapsed whitespace, lowercased) for grouping but displayed in their
    original casing. Only messages asked more than once qualify — a
    knowledge base's worth of once-off questions isn't a "most common"
    list, it's just a list of everything anyone ever asked.
    """
    texts = Message.objects.filter(
        tenant=tenant, sender_type=Message.SenderType.CUSTOMER, direction=Message.Direction.INBOUND
    )
    texts = (
        _date_bounded(texts, "created_at", start, end)
        .exclude(content="")
        .values_list("content", flat=True)
    )

    counter = Counter()
    display_text = {}
    for content in texts:
        normalized = _WHITESPACE.sub(" ", content.strip().lower())
        if not normalized:
            continue
        counter[normalized] += 1
        display_text.setdefault(normalized, content.strip())

    return [
        {"text": display_text[normalized], "count": count}
        for normalized, count in counter.most_common(limit)
        if count > 1
    ]


def business_dashboard(tenant, start=None, end=None) -> dict:
    """The single per-tenant dashboard payload — see docs/analytics.md."""
    return {
        "funnel": customer_funnel(tenant, start, end),
        "conversations": conversation_counts(tenant, start, end),
        "messages": message_counts(tenant, start, end),
        "orders": order_revenue(tenant, start, end),
        "ai": ai_performance(tenant, start, end),
        "response_time": average_response_time(tenant, start, end),
        "top_questions": top_customer_questions(tenant, start, end),
    }
