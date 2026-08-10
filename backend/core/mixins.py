"""
WhatsAppBusinessAI — Core Mixins
Reusable DRF generic-view mixins for tenant-scoped resources.
"""

from rest_framework.exceptions import ValidationError


class TenantScopedQuerysetMixin:
    """
    Scopes the queryset to the caller's own tenant — never to a tenant id
    supplied by the client. Super admins see everything (platform oversight).
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(tenant_id=user.tenant_id)


class TenantScopedCreateMixin:
    """
    Injects the caller's own tenant on create — never accepts one from the
    client. Super admins have no tenant of their own (spec section 6 — they
    manage the platform, not a business), so creating tenant-scoped data
    directly isn't a meaningful action for them here; reject with a clear
    400 instead of hitting the model's NOT NULL constraint.
    """

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if tenant is None:
            raise ValidationError(
                "A super admin has no tenant of their own and cannot create this directly."
            )
        serializer.save(tenant=tenant)
