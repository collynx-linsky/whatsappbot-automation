"""
WhatsAppBusinessAI — Common / Shared Platform Models

AuditLog — platform-wide audit trail (spec section 19). Every significant
administrative action should eventually log here; this phase wires the
model and a `log()` helper — later phases call it from their services as
each domain (WhatsApp, products, orders, campaigns, ...) lands.
"""

import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=50, db_index=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=255, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(max_length=200, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "common_audit_log"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "action", "created_at"])]

    def __str__(self):
        who = self.user.email if self.user else "system"
        return f"{self.action} by {who} at {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def log(cls, *, action, user=None, tenant=None, obj=None, metadata=None, ip_address=None):
        """Convenience helper — services call `AuditLog.log(action=..., user=..., obj=...)`."""
        content_type = None
        object_id = ""
        object_repr = ""
        if obj is not None:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = str(obj.pk)
            object_repr = str(obj)[:200]
        return cls.objects.create(
            action=action,
            user=user,
            tenant=tenant or getattr(user, "tenant", None),
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            metadata=metadata or {},
            ip_address=ip_address,
        )
