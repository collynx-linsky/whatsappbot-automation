"""
WhatsAppBusinessAI — Message Models

Message/MessageAttachment per spec section 8. MessageEvent (the webhook
dedup log) is deliberately not built here — it exists specifically to make
*webhook* processing idempotent, and only makes sense once Phase 7 adds a
real webhook receiver. `external_message_id` is present now so Phase 7 can
write into it without another migration.
"""

from django.db import models

from core.models import BaseModel


class Message(BaseModel):
    class SenderType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        STAFF = "staff", "Staff"
        AI = "ai", "AI Assistant"
        SYSTEM = "system", "System"

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"
        LOCATION = "location", "Location"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        READ = "read", "Read"
        FAILED = "failed", "Failed"

    conversation = models.ForeignKey(
        "conversations.Conversation", on_delete=models.CASCADE, related_name="messages"
    )
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    sender_user = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    message_type = models.CharField(
        max_length=20, choices=MessageType.choices, default=MessageType.TEXT
    )
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)

    # Populated once a real messaging provider (WhatsApp, Phase 7) is wired
    # in — used for webhook-delivery dedup and provider-side status lookups.
    external_message_id = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        db_table = "messaging_message"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["tenant", "conversation", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "external_message_id"],
                condition=~models.Q(external_message_id=""),
                name="unique_external_message_id_per_tenant",
            ),
        ]

    def __str__(self):
        return f"[{self.direction}] {self.content[:50]}"


class MessageAttachment(BaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="messages/attachments/%Y/%m/")
    file_name = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0, help_text="Bytes")

    class Meta:
        db_table = "messaging_attachment"
        ordering = ["-created_at"]

    def __str__(self):
        return self.file_name or self.file.name
