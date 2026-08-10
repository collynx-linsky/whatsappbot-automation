"""
WhatsAppBusinessAI — WhatsApp Integration Models

WhatsAppAccount per spec section 7 — the access token is encrypted at rest
(core.crypto) and NEVER serialized back out via the API (see
serializers.py). MessageEvent is the webhook idempotency log deferred from
Phase 6 — WhatsApp (and Meta in general) can and does redeliver the same
webhook event; without this, a retried delivery would create a duplicate
inbound message.
"""

from django.db import models

from core.crypto import decrypt_secret, encrypt_secret
from core.models import BaseModel


class WhatsAppAccount(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Verification"
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        ERROR = "error", "Error"

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="whatsapp_accounts"
    )

    display_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(
        max_length=20, help_text="E.164 display number, e.g. +254712345678"
    )
    phone_number_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Meta's numeric ID for this phone number — identifies the account on inbound webhooks.",
    )
    business_account_id = models.CharField(
        max_length=100, help_text="WhatsApp Business Account (WABA) ID."
    )

    # Encrypted at rest; access via the .access_token property, never the
    # raw field. Never included in any serializer output.
    access_token_encrypted = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "whatsapp_account"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"{self.phone_number} ({self.business.name})"

    @property
    def access_token(self) -> str:
        return decrypt_secret(self.access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str):
        self.access_token_encrypted = encrypt_secret(value)

    def mark_connected(self):
        from django.utils import timezone

        self.status = self.Status.CONNECTED
        self.connected_at = timezone.now()
        self.last_error = ""
        self.save(update_fields=["status", "connected_at", "last_error", "updated_at"])

    def mark_error(self, message: str):
        self.status = self.Status.ERROR
        self.last_error = message[:500]
        self.save(update_fields=["status", "last_error", "updated_at"])


class MessageEvent(BaseModel):
    """
    Webhook delivery idempotency log — one row per distinct WhatsApp
    message/status event actually processed. Meta redelivers webhooks on
    timeout/error; without this a retry would create a duplicate Message.
    """

    whatsapp_account = models.ForeignKey(
        WhatsAppAccount, on_delete=models.CASCADE, related_name="events"
    )
    external_event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="WhatsApp's wamid.* message id, or a status-event key.",
    )
    event_type = models.CharField(max_length=30, default="message")
    raw_payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "whatsapp_message_event"
        ordering = ["-processed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["whatsapp_account", "external_event_id"], name="unique_event_per_account"
            ),
        ]

    def __str__(self):
        return f"{self.event_type}:{self.external_event_id}"
