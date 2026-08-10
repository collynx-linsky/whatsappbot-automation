"""WhatsAppBusinessAI — Products Views"""

from rest_framework import generics

from apps.common.models import AuditLog
from core.mixins import TenantScopedCreateMixin, TenantScopedQuerysetMixin
from core.permissions import IsManagerOrAbove, IsStaffOrAbove

from .models import Product
from .serializers import ProductSerializer


class ProductListCreateView(
    TenantScopedQuerysetMixin, TenantScopedCreateMixin, generics.ListCreateAPIView
):
    """
    GET /api/v1/products/ — catalog for the caller's own tenant (staff+,
    so front-line staff can answer product questions).
    POST /api/v1/products/ — manager+ (inventory/catalog is a management action).
    """

    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    filterset_fields = ["status", "category", "is_available"]
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["name", "price", "created_at"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]

    def perform_create(self, serializer):
        # Reuse TenantScopedCreateMixin's guard (rejects a tenant-less
        # super admin) via super(), then log explicitly here — not a
        # post_save signal — so the audit entry can record *who* made the
        # change; a signal has no access to request.user.
        super().perform_create(serializer)
        product = serializer.instance
        AuditLog.log(
            action="PRODUCT_CREATED",
            user=self.request.user,
            tenant=product.tenant,
            obj=product,
            metadata={"name": product.name, "price": str(product.price)},
        )


class ProductDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/products/{id}/"""

    serializer_class = ProductSerializer
    queryset = Product.objects.all()

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsStaffOrAbove()]
        return [IsManagerOrAbove()]

    def perform_update(self, serializer):
        product = serializer.save()
        AuditLog.log(
            action="PRODUCT_UPDATED",
            user=self.request.user,
            tenant=product.tenant,
            obj=product,
            metadata={"name": product.name, "price": str(product.price), "status": product.status},
        )
