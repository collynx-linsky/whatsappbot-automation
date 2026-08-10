"""
WhatsAppBusinessAI — Core Abstract Models

Every tenant-scoped domain model (customers, conversations, products, ...)
should inherit from BaseModel. These are abstract classes — they add no
tables of their own.
"""

import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Provides created_at and updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """Default manager — excludes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Manager that includes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset()


class SoftDeleteModel(models.Model):
    """Provides soft-delete instead of hard deletion."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, deleted_by=None, *args, **kwargs):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if deleted_by:
            self.deleted_by = deleted_by
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def hard_delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


class TenantAwareManager(SoftDeleteManager):
    """Manager that can filter explicitly by tenant.

    NOTE: this does NOT auto-filter every query by the "current" tenant —
    that would make it too easy to silently trust request-derived state.
    Views/services must call `.for_tenant(request.tenant)` (or filter by
    tenant explicitly) after resolving the tenant server-side. See
    docs/multi-tenancy.md.
    """

    def for_tenant(self, tenant):
        return self.get_queryset().filter(tenant=tenant)


class TenantAwareModel(TimeStampedModel, SoftDeleteModel):
    """Base model for all tenant-scoped data."""

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    objects = TenantAwareManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True


class AuditedModel(models.Model):
    """Tracks who created and last modified the record."""

    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class BaseModel(TenantAwareModel, AuditedModel):
    """
    Full base model combining UUID pk, tenant isolation, soft delete,
    timestamps, and audit fields. Domain models in later phases (customers,
    conversations, products, ...) should inherit from this.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
