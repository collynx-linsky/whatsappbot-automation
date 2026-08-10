"""WhatsAppBusinessAI — AI Celery Tasks"""

import logging

from celery import shared_task

logger = logging.getLogger("waba")


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def generate_ai_response_task(self, message_id: str):
    """Generates (or hands off) the AI's reply to one inbound customer message."""
    from apps.ai.services import generate_ai_reply
    from apps.messages.models import Message

    try:
        message = Message.objects.select_related("conversation__tenant").get(pk=message_id)
    except Message.DoesNotExist:
        logger.warning("generate_ai_response_task: message %s no longer exists.", message_id)
        return

    generate_ai_reply(message)
