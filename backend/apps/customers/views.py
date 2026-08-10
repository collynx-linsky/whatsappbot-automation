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


class CustomerDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/customers/{id}/"""

    permission_classes = [IsStaffOrAbove]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
