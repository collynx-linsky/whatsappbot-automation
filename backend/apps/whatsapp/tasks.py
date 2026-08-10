"""WhatsAppBusinessAI — WhatsApp Celery Tasks"""

import logging

from celery import shared_task

logger = logging.getLogger("waba")


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_whatsapp_message_task(self, message_id: str):
    """
    Sends a staff-authored Message out via the business's connected
    WhatsAppAccount. No-ops (logs and returns) if the tenant has no
    connected account yet — the message still exists as a normal in-app
    reply, it just never reaches WhatsApp.
    """
    from apps.messages.models import Message
    from apps.whatsapp.models import WhatsAppAccount
    from apps.whatsapp.providers import WhatsAppCloudProvider

    try:
        message = Message.objects.select_related("conversation__customer", "tenant").get(
            pk=message_id
        )
    except Message.DoesNotExist:
        logger.warning("send_whatsapp_message_task: message %s no longer exists.", message_id)
        return

    account = (
        WhatsAppAccount.objects.filter(
            tenant=message.tenant, status=WhatsAppAccount.Status.CONNECTED
        )
        .order_by("-created_at")
        .first()
    )
    if account is None:
        logger.info(
            "send_whatsapp_message_task: no connected WhatsApp account for tenant %s — skipping.",
            message.tenant_id,
        )
        return

    provider = WhatsAppCloudProvider(
        phone_number_id=account.phone_number_id, access_token=account.access_token
    )
    result = provider.send_text_message(
        to=message.conversation.customer.phone, text=message.content
    )

    if result["success"]:
        message.status = Message.Status.SENT
        message.external_message_id = result["external_id"] or ""
        message.save(update_fields=["status", "external_message_id", "updated_at"])
    else:
        message.status = Message.Status.FAILED
        message.save(update_fields=["status", "updated_at"])
        logger.warning("WhatsApp send failed for message %s: %s", message_id, result["error"])
