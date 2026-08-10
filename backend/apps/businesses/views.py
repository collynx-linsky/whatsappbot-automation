"""WhatsAppBusinessAI — Businesses Views"""

from rest_framework import generics, permissions

from core.mixins import TenantScopedQuerysetMixin
from core.permissions import IsManagerOrAbove, IsStaffOrAbove

from .models import Business
from .serializers import BusinessSerializer


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
