"""WhatsAppBusinessAI — Customers Views"""

from rest_framework import generics

from core.mixins import TenantScopedCreateMixin, TenantScopedQuerysetMixin
from core.permissions import IsStaffOrAbove

from .models import Customer
from .serializers import CustomerSerializer


class CustomerListCreateView(
    TenantScopedQuerysetMixin, TenantScopedCreateMixin, generics.ListCreateAPIView
):
    """GET/POST /api/v1/customers/ — customers in the caller's own tenant."""

    permission_classes = [IsStaffOrAbove]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
    filterset_fields = ["status", "source"]
    search_fields = ["name", "phone", "email"]
    ordering_fields = ["created_at", "last_interaction_at", "name"]

    def perform_create(self, serializer):
        # Only enforced on this manually-initiated API path — a real
        # inbound WhatsApp message from a new customer (apps.whatsapp's
        # webhook-driven get_or_create) is never blocked by a plan limit;
        # dropping a genuine customer inquiry over a quota would be a
        # worse outcome than a business briefly exceeding its plan. See
        # docs/billing.md.
        from apps.billing.services import check_limit

        check_limit(self.request.user.tenant, "customers")
        super().perform_create(serializer)


class CustomerDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/customers/{id}/"""

    permission_classes = [IsStaffOrAbove]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
