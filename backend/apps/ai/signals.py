"""
WhatsAppBusinessAI — AI Signals

Listens for inbound customer messages and dispatches AI reply generation.
Lives here (not in apps.messages or apps.whatsapp) so neither of those
apps needs to know the AI engine exists — same decoupling pattern as
apps.whatsapp.signals for outbound sending.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.messages.models import Message

logger = logging.getLogger("waba")


@receiver(post_save, sender=Message)
def dispatch_ai_reply(sender, instance, created, **kwargs):
    if not created or instance.direction != Message.Direction.INBOUND:
        return
    if instance.sender_type != Message.SenderType.CUSTOMER:
        return

    from .tasks import generate_ai_response_task

    try:
        generate_ai_response_task.delay(str(instance.id))
    except Exception:
        # Broker unreachable shouldn't break inbound message storage — the
        # message just sits unanswered until a human notices. Same
        # resilience posture as apps.whatsapp.signals.
        logger.exception(
            "Could not enqueue generate_ai_response_task for message %s — broker unreachable?",
            instance.id,
        )
