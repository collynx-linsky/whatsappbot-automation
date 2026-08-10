"""
WhatsAppBusinessAI — Business Model

The actual WhatsApp business profile a Tenant operates. Fields per spec
section 7. WhatsAppAccount, staff assignment, and AI/knowledge config are
built on top of this in later phases (7, 8, 12).
"""

import uuid

from django.db import models


class Business(models.Model):
    class Category(models.TextChoices):
        RETAIL = "retail", "Retail"
        ELECTRONICS = "electronics", "Electronics"
        FASHION = "fashion", "Fashion & Apparel"
        FOOD_BEVERAGE = "food_beverage", "Food & Beverage"
        HEALTH_BEAUTY = "health_beauty", "Health & Beauty"
        SERVICES = "services", "Professional Services"
        EDUCATION = "education", "Education"
        AGRICULTURE = "agriculture", "Agriculture"
        REAL_ESTATE = "real_estate", "Real Estate"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="businesses"
    )

    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Kenya")
    timezone = models.CharField(max_length=50, default="Africa/Nairobi")
    currency = models.CharField(max_length=3, default="KES")

    logo = models.ImageField(upload_to="businesses/logos/", null=True, blank=True)

    # e.g. {"mon": {"open": "08:00", "close": "18:00"}, "tue": {...}, ...}
    opening_hours = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "businesses_business"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
