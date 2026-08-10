"""
WhatsAppBusinessAI — WhatsApp Signals

Listens for outbound staff *and* AI-authored messages and dispatches them
to WhatsApp. Lives here (not in apps.messages or apps.ai) so the core
messaging app has zero knowledge that WhatsApp exists, and the AI engine
has zero knowledge of how (or whether) its replies actually get delivered
— a future provider app would listen the same way.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.messages.models import Message

logger = logging.getLogger("waba")

# Both a human staff reply and an AI-generated reply need to reach the
# customer on WhatsApp. SYSTEM messages (e.g. an internal handoff note)
# deliberately do not — see apps.ai.services._hand_off.
_SENDABLE_SENDER_TYPES = (Message.SenderType.STAFF, Message.SenderType.AI)


@receiver(post_save, sender=Message)
def dispatch_outbound_message(sender, instance, created, **kwargs):
    if not created or instance.direction != Message.Direction.OUTBOUND:
        return
    if instance.sender_type not in _SENDABLE_SENDER_TYPES:
        return

    from .tasks import send_whatsapp_message_task

    try:
        send_whatsapp_message_task.delay(str(instance.id))
    except Exception:
        # Broker unreachable (e.g. Redis/Docker down) shouldn't break
        # message creation — the message just stays PENDING until someone
        # retries. Log loudly since a silently-stuck PENDING message is a
        # real support issue if this happens in production.
        logger.exception(
            "Could not enqueue send_whatsapp_message_task for message %s — broker unreachable?",
            instance.id,
        )
