"""
WhatsAppBusinessAI — WhatsApp Webhook Processing Service

Implements the inbound flow from spec section 9:
WhatsApp -> Webhook -> validate -> identify account -> identify tenant ->
identify customer -> create/update conversation -> store message ->
[AI/human handling -> Phase 8; nothing acts on ai_enabled yet]
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.db import IntegrityError, transaction

from apps.conversations.models import Conversation
from apps.customers.models import Customer
from apps.messages.models import Message

from .models import MessageEvent, WhatsAppAccount
from .providers import parse_webhook_payload

logger = logging.getLogger("waba")

_MESSAGE_TYPE_MAP = {
    "text": Message.MessageType.TEXT,
    "image": Message.MessageType.IMAGE,
    "document": Message.MessageType.DOCUMENT,
    "audio": Message.MessageType.AUDIO,
    "video": Message.MessageType.VIDEO,
    "location": Message.MessageType.LOCATION,
}


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Verifies Meta's `X-Hub-Signature-256` header — `sha256=<hex hmac>` of
    the raw request body, keyed by WHATSAPP_APP_SECRET. Constant-time
    compare (timing-attack resistant).
    """
    if not settings.WHATSAPP_APP_SECRET:
        # Fail closed: no configured secret means we can't verify anything,
        # so reject rather than silently accept unsigned webhook traffic.
        logger.warning("WHATSAPP_APP_SECRET is not configured — rejecting webhook.")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def process_webhook_payload(payload: dict) -> int:
    """Processes one webhook POST body. Returns the number of messages actually created."""
    created_count = 0
    for event in parse_webhook_payload(payload):
        if _process_single_event(event, payload):
            created_count += 1
    return created_count


def _process_single_event(event: dict, raw_payload: dict) -> bool:
    phone_number_id = event.get("phone_number_id")
    message_id = event.get("message_id")
    if not phone_number_id or not message_id:
        logger.warning("Webhook event missing phone_number_id/message_id — skipping: %s", event)
        return False

    account = (
        WhatsAppAccount.objects.filter(phone_number_id=phone_number_id)
        .select_related("tenant")
        .first()
    )
    if account is None:
        # Never trust the payload to tell us which tenant this is for — the
        # only way to resolve a tenant here is through a phone_number_id we
        # ourselves stored when the business connected their number.
        logger.warning("Webhook for unknown phone_number_id=%s — skipping.", phone_number_id)
        return False

    try:
        with transaction.atomic():
            # Idempotency guard: unique (account, external_event_id). Meta
            # redelivers webhooks on timeout — a duplicate delivery hits
            # this constraint and the whole block rolls back cleanly.
            MessageEvent.objects.create(
                tenant=account.tenant,
                whatsapp_account=account,
                external_event_id=message_id,
                event_type="message",
                raw_payload=raw_payload,
            )

            customer, _ = Customer.objects.get_or_create(
                tenant=account.tenant,
                phone=event["wa_id"],
                defaults={
                    "name": event.get("contact_name", ""),
                    "source": Customer.Source.WHATSAPP,
                },
            )

            conversation = (
                Conversation.objects.filter(tenant=account.tenant, customer=customer)
                .exclude(status=Conversation.Status.CLOSED)
                .order_by("-created_at")
                .first()
            )
            if conversation is None:
                conversation = Conversation.objects.create(
                    tenant=account.tenant, customer=customer
                )

            message = Message.objects.create(
                tenant=account.tenant,
                conversation=conversation,
                sender_type=Message.SenderType.CUSTOMER,
                direction=Message.Direction.INBOUND,
                message_type=_MESSAGE_TYPE_MAP.get(
                    event["message_type"], Message.MessageType.TEXT
                ),
                content=event.get("text", ""),
                status=Message.Status.DELIVERED,
                external_message_id=message_id,
            )
            conversation.record_message(message)
            customer.touch_interaction()
    except IntegrityError:
        logger.info(
            "Duplicate webhook event %s for account %s — already processed.",
            message_id,
            account.id,
        )
        return False

    return True
