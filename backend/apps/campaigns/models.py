"""
WhatsAppBusinessAI — Marketing Campaigns Models (spec section 12)

    MessageTemplate   a business's WhatsApp-approved message templates
    Segment           a saved, dynamically-evaluated customer filter
    Campaign          one bulk send of one Template to one Segment
        `-- CampaignRecipient[]   per-customer send outcome

Compliance is the whole point of this app, not an afterthought — see
docs/campaigns.md. Two rules enforced structurally, not just by convention:
(1) a Campaign can only use an `approved` Template (WhatsApp does not allow
proactive marketing sends as free text, template or not, outside a
customer-initiated session), and (2) `Segment.get_customers()` always
filters to `marketing_opt_in=True`, so a segment's own recipient count is
never a lie about who will actually be messaged.
"""

import re

from django.db import models

from core.models import BaseModel

_VARIABLE_PATTERN = re.compile(r"\{\{(\d+)\}\}")


class MessageTemplate(BaseModel):
    """
    A business's own record of a WhatsApp message template. Meta requires
    templates to be submitted and approved through their own Business
    Manager / Template API before they can be used — this project has no
    real Meta credentials, so `status` is set manually by whoever actually
    did that approval in Meta's system, not queried live. See
    docs/campaigns.md.
    """

    class Category(models.TextChoices):
        MARKETING = "marketing", "Marketing"
        UTILITY = "utility", "Utility"
        AUTHENTICATION = "authentication", "Authentication"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="message_templates"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    name = models.CharField(max_length=255, help_text="Internal display name.")
    whatsapp_template_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="The exact name registered with Meta. Blank until submitted for approval.",
    )
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.MARKETING
    )
    language_code = models.CharField(max_length=10, default="en_US")
    body_text = models.TextField(
        help_text="Template body with {{1}}, {{2}}, ... placeholders, matching Meta's own syntax."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        db_table = "campaigns_message_template"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "business", "status"])]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def variable_count(self) -> int:
        """How many distinct {{n}} placeholders body_text declares."""
        numbers = {int(n) for n in _VARIABLE_PATTERN.findall(self.body_text)}
        return len(numbers)


class Segment(BaseModel):
    """
    A saved, dynamically-evaluated customer filter — re-evaluated every
    time it's used (a Campaign snapshots its recipient list at send time,
    not at Segment-creation time), so a Segment always reflects the
    current customer base, not a stale list.
    """

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="segments"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Supported keys: "statuses" (list of Customer.Status values, any-match),
    # "tags" (list of strings, any-match against Customer.tags),
    # "sources" (list of Customer.Source values, any-match). An empty dict
    # matches every opted-in customer of the business.
    filters = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "campaigns_segment"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "business"])]

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class Campaign(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="campaigns"
    )
    segment = models.ForeignKey(Segment, on_delete=models.PROTECT, related_name="campaigns")
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.PROTECT, related_name="campaigns"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    name = models.CharField(max_length=255)
    # Positional values substituted into the template's {{1}}, {{2}}, ...
    # for EVERY recipient — no per-recipient personalization this phase
    # (see docs/campaigns.md's limitations).
    template_variables = models.JSONField(default=list, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "campaigns_campaign"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "business", "status"])]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class CampaignRecipient(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="recipients")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="campaign_recipients"
    )
    # NOTE: the app label for apps.messages is "messaging", not "messages"
    # (that label is taken by django.contrib.messages) — see
    # apps/messages/apps.py. Using "messages.Message" here resolves to
    # nothing and fails silently until something dereferences it.
    message = models.OneToOneField(
        "messaging.Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_recipient",
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    skip_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. 'not opted in', 'no connected WhatsApp account'.",
    )
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "campaigns_recipient"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["tenant", "campaign", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "customer"], name="unique_customer_per_campaign"
            ),
        ]

    def __str__(self):
        return f"{self.customer} in {self.campaign.name} ({self.status})"
