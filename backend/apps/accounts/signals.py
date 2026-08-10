"""WhatsAppBusinessAI — Accounts Signals"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def audit_log_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.common.models import AuditLog

    AuditLog.log(
        action="USER_CREATED",
        user=instance,
        tenant=instance.tenant,
        obj=instance,
        metadata={"role": instance.role, "email": instance.email},
    )
