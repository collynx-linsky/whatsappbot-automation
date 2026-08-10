"""WhatsAppBusinessAI — Customers Signals"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Customer


@receiver(post_save, sender=Customer)
def audit_log_customer_created(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.common.models import AuditLog

    AuditLog.log(
        action="CUSTOMER_CREATED",
        tenant=instance.tenant,
        obj=instance,
        metadata={"phone": instance.phone, "source": instance.source},
    )
