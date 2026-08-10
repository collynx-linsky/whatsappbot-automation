"""WhatsAppBusinessAI — Campaign Celery Tasks"""

import logging

from celery import shared_task

logger = logging.getLogger("waba")


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def send_campaign_task(self, campaign_id: str):
    """Sends one Campaign to every opted-in recipient in its Segment."""
    from apps.campaigns.models import Campaign
    from apps.campaigns.services import send_campaign

    try:
        campaign = Campaign.objects.select_related("business", "segment", "template").get(
            pk=campaign_id
        )
    except Campaign.DoesNotExist:
        logger.warning("send_campaign_task: campaign %s no longer exists.", campaign_id)
        return

    send_campaign(campaign)
