"""
WhatsAppBusinessAI — Conversation Models

Conversation fields per spec section 8. Scoped down for this phase: a
conversation has exactly one customer and at most one assigned staff
member (sufficient for 1:1 WhatsApp chat) rather than a full
ConversationParticipant model for multi-party conversations — see
docs/ROADMAP.md if that's ever actually needed. ConversationAssignment
exists as an assignment *history* log (who was assigned when), separate
from Conversation.assigned_to which is just "who's on it right now."
"""

from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Conversation(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="conversations"
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    assigned_to = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
    )
    ai_enabled = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)

    last_message_preview = models.CharField(max_length=255, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "conversations_conversation"
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "assigned_to"]),
        ]

    def __str__(self):
        return f"Conversation with {self.customer} ({self.status})"

    def assign_to(self, user, assigned_by=None):
        """Assign staff to this conversation and log the change."""
        previous = self.assigned_to
        if previous == user:
            return
        if previous:
            ConversationAssignment.objects.filter(
                conversation=self, user=previous, unassigned_at__isnull=True
            ).update(unassigned_at=timezone.now())
        self.assigned_to = user
        self.save(update_fields=["assigned_to", "updated_at"])
        if user:
            ConversationAssignment.objects.create(
                tenant=self.tenant, conversation=self, user=user, assigned_by=assigned_by
            )

    def record_message(self, message):
        """Update the conversation's preview/last-activity fields after a new message."""
        self.last_message_preview = message.content[:255]
        self.last_message_at = message.created_at
        if message.direction == message.Direction.INBOUND:
            self.unread_count += 1
        self.save(
            update_fields=["last_message_preview", "last_message_at", "unread_count", "updated_at"]
        )


class ConversationAssignment(BaseModel):
    """History log of staff assignment on a conversation."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="assignment_history"
    )
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="+")
    assigned_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "conversations_assignment"
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.user} on {self.conversation_id}"
