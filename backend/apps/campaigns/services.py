"""
WhatsAppBusinessAI — Campaign Send Orchestration (spec sections 12, 26)

prepare_campaign_recipients() snapshots a Segment's current customer list
onto a Campaign (so "who got this campaign" is a durable historical
record, not a live re-evaluation of the segment days later).
send_campaign() is the actual bulk-send loop, run from a Celery task.

Compliance is enforced at two points, not one: `get_segment_customers`
excludes non-opted-in customers when the segment is first evaluated, and
`send_campaign` re-checks `marketing_opt_in` per recipient at send time —
a customer who opts out between when a campaign was scheduled and when it
actually sends must never receive it anyway.
"""

import logging

from django.db.models import Q
from django.utils import timezone

from apps.conversations.models import Conversation
from apps.customers.models import Customer
from apps.messages.models import Message
from apps.whatsapp.models import WhatsAppAccount
from apps.whatsapp.providers import WhatsAppCloudProvider

from .models import Campaign, CampaignRecipient, MessageTemplate, Segment

logger = logging.getLogger("waba")


def get_segment_customers(segment: Segment):
    """
    Evaluates `segment.filters` against the business's own customers.
    Always filters to `marketing_opt_in=True` — a Segment's recipient
    count must never overstate who can actually be messaged (spec
    section 26's compliance requirement, enforced structurally here
    rather than left to campaign-send-time to catch).
    """
    qs = Customer.objects.filter(tenant=segment.tenant, marketing_opt_in=True)
    statuses = segment.filters.get("statuses")
    if statuses:
        qs = qs.filter(status__in=statuses)
    sources = segment.filters.get("sources")
    if sources:
        qs = qs.filter(source__in=sources)
    tags = segment.filters.get("tags")
    if tags:
        tag_query = Q()
        for tag in tags:
            tag_query |= Q(tags__contains=[tag])
        qs = qs.filter(tag_query)
    return qs.distinct()


def prepare_campaign_recipients(campaign: Campaign) -> int:
    """
    Snapshots the segment's current customers onto CampaignRecipient rows
    (idempotent — safe to call again on a campaign that already has some).
    Returns the total recipient count.
    """
    customers = get_segment_customers(campaign.segment)
    existing_customer_ids = set(campaign.recipients.values_list("customer_id", flat=True))
    new_recipients = [
        CampaignRecipient(tenant=campaign.tenant, campaign=campaign, customer=customer)
        for customer in customers
        if customer.id not in existing_customer_ids
    ]
    if new_recipients:
        CampaignRecipient.objects.bulk_create(new_recipients)

    count = campaign.recipients.count()
    campaign.recipient_count = count
    campaign.save(update_fields=["recipient_count", "updated_at"])
    return count


def _render_preview(template: MessageTemplate, params: list[str]) -> str:
    """Best-effort {{n}} substitution for the Message.content we store — Meta's own
    rendering of the actual template is authoritative; this is just for our own records."""
    text = template.body_text
    for i, value in enumerate(params, start=1):
        text = text.replace(f"{{{{{i}}}}}", str(value))
    return text


def send_campaign(campaign: Campaign) -> None:
    """
    Sends `campaign` to every PENDING recipient. Structural problems (no
    approved template, no connected WhatsApp account, zero recipients)
    fail the whole campaign before attempting any sends; per-recipient
    problems (opted out since scheduling, a provider error) only fail
    that one recipient — the rest of the batch still goes out.
    """
    campaign.status = Campaign.Status.SENDING
    campaign.started_at = timezone.now()
    campaign.save(update_fields=["status", "started_at", "updated_at"])

    if campaign.template.status != MessageTemplate.Status.APPROVED:
        _fail_campaign(campaign, "Template is not approved.")
        return

    account = (
        WhatsAppAccount.objects.filter(
            tenant=campaign.tenant, status=WhatsAppAccount.Status.CONNECTED
        )
        .order_by("-created_at")
        .first()
    )
    if account is None:
        _fail_campaign(campaign, "No connected WhatsApp account for this business.")
        return

    prepare_campaign_recipients(campaign)
    recipients = list(campaign.recipients.filter(status=CampaignRecipient.Status.PENDING))
    if not recipients:
        _fail_campaign(campaign, "Segment has no opted-in customers.")
        return

    from apps.billing.services import increment_usage

    increment_usage(campaign.tenant, "campaign_sends")

    provider = WhatsAppCloudProvider(
        phone_number_id=account.phone_number_id, access_token=account.access_token
    )
    preview_text = _render_preview(campaign.template, campaign.template_variables)

    for recipient in recipients:
        _send_to_recipient(campaign, recipient, provider, preview_text)

    campaign.status = Campaign.Status.SENT
    campaign.completed_at = timezone.now()
    campaign.save(
        update_fields=[
            "status",
            "completed_at",
            "sent_count",
            "failed_count",
            "skipped_count",
            "updated_at",
        ]
    )
    logger.info(
        "Campaign %s finished: %s sent, %s failed, %s skipped.",
        campaign.id,
        campaign.sent_count,
        campaign.failed_count,
        campaign.skipped_count,
    )


def _send_to_recipient(campaign, recipient, provider, preview_text):
    customer = recipient.customer

    # Re-checked here, not just at segment-evaluation time — see module docstring.
    if not customer.marketing_opt_in:
        recipient.status = CampaignRecipient.Status.SKIPPED
        recipient.skip_reason = "not opted in"
        recipient.save(update_fields=["status", "skip_reason", "updated_at"])
        campaign.skipped_count += 1
        return

    result = provider.send_template_message(
        to=customer.phone,
        template_name=campaign.template.whatsapp_template_name,
        language_code=campaign.template.language_code,
        body_params=[str(v) for v in campaign.template_variables],
    )

    conversation = (
        Conversation.objects.filter(tenant=campaign.tenant, customer=customer)
        .exclude(status=Conversation.Status.CLOSED)
        .order_by("-created_at")
        .first()
    )
    if conversation is None:
        conversation = Conversation.objects.create(tenant=campaign.tenant, customer=customer)

    message = Message.objects.create(
        tenant=campaign.tenant,
        conversation=conversation,
        sender_type=Message.SenderType.CAMPAIGN,
        direction=Message.Direction.OUTBOUND,
        content=preview_text,
        status=Message.Status.SENT if result["success"] else Message.Status.FAILED,
        external_message_id=result["external_id"] or "",
    )
    conversation.record_message(message)

    recipient.message = message
    recipient.sent_at = timezone.now()
    if result["success"]:
        recipient.status = CampaignRecipient.Status.SENT
        campaign.sent_count += 1
    else:
        recipient.status = CampaignRecipient.Status.FAILED
        recipient.error_message = result["error"] or ""
        campaign.failed_count += 1
    recipient.save(update_fields=["message", "sent_at", "status", "error_message", "updated_at"])


def _fail_campaign(campaign: Campaign, reason: str) -> None:
    campaign.status = Campaign.Status.FAILED
    campaign.error_message = reason
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
    logger.warning("Campaign %s failed to send: %s", campaign.id, reason)
