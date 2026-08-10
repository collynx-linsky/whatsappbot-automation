"""
WhatsAppBusinessAI — Tenant & Plan Models

Tenant is the platform's multi-tenancy isolation boundary (the account a
business signs up under). Business (apps.businesses.Business) is the actual
WhatsApp business profile that belongs to a Tenant — most tenants have
exactly one Business in the MVP, but the model supports more later.
"""

import uuid

from django.db import models
from django.utils.text import slugify


class Plan(models.Model):
    """
    A SaaS subscription plan. Plans are database-configurable (not
    hardcoded) — see spec section 24. Only the shape is built this phase;
    billing/invoicing logic lands with apps.billing in a later phase.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)

    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")

    # Usage limits — 0 means unlimited.
    max_users = models.IntegerField(default=5)
    max_whatsapp_accounts = models.IntegerField(default=1)
    max_ai_messages_per_month = models.IntegerField(default=1000)
    max_customers = models.IntegerField(default=1000)
    max_campaigns_per_month = models.IntegerField(default=10)
    max_storage_mb = models.IntegerField(default=1024)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False, help_text="Plan assigned to new tenants when none is specified."
    )
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_plans"
        ordering = ["sort_order", "price_monthly"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tenant(models.Model):
    """The central multi-tenancy model — every Business and User belongs to one."""

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRIAL, db_index=True
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="tenants", null=True)

    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_tenant"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            i = 1
            while Tenant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base_slug}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        return self.status in (self.Status.TRIAL, self.Status.ACTIVE)
