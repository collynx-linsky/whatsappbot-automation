"""
WhatsAppBusinessAI — Customer CRM Models

Customer fields per spec section 7/15. `tags` is a simple JSON list of
strings rather than a normalized Tag model — enough for filtering/display
without building a tag taxonomy this phase (see docs/ROADMAP.md).
"""

from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Customer(BaseModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal"
        CONVERTED = "converted", "Converted"
        LOST = "lost", "Lost"

    class Source(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        WEBSITE = "website", "Website"
        REFERRAL = "referral", "Referral"
        WALK_IN = "walk_in", "Walk-in"
        CAMPAIGN = "campaign", "Campaign"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="List of free-text tag strings.")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WHATSAPP)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    notes = models.TextField(blank=True)
    last_interaction_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "customers_customer"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "phone"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "phone"], name="unique_customer_phone_per_tenant"
            ),
        ]

    def __str__(self):
        return f"{self.name or self.phone} ({self.get_status_display()})"

    def touch_interaction(self):
        self.last_interaction_at = timezone.now()
        self.save(update_fields=["last_interaction_at"])
