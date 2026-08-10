"""WhatsAppBusinessAI — Businesses Views"""

from rest_framework import generics, permissions

from core.permissions import IsManagerOrAbove, IsStaffOrAbove

from .models import Business
from .serializers import BusinessSerializer


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


class BusinessListView(TenantScopedQuerysetMixin, generics.ListAPIView):
    """GET /api/v1/businesses/ — businesses in the caller's own tenant."""

    permission_classes = [IsStaffOrAbove]
    serializer_class = BusinessSerializer
    queryset = Business.objects.select_related("tenant").all()


class BusinessDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/businesses/{id}/"""

    serializer_class = BusinessSerializer
    queryset = Business.objects.select_related("tenant").all()

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAbove()]
        return [IsManagerOrAbove()]
