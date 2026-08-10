"""WhatsAppBusinessAI — Orders Views"""

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.models import AuditLog
from core.mixins import TenantScopedQuerysetMixin
from core.permissions import IsStaffOrAbove

from .models import Order, OrderItem
from .serializers import OrderCreateSerializer, OrderSerializer, UpdateOrderStatusSerializer


class OrderListCreateView(TenantScopedQuerysetMixin, generics.ListCreateAPIView):
    """
    GET /api/v1/orders/ — orders in the caller's own tenant.
    POST /api/v1/orders/ — create an order with line items in one call;
    always starts PENDING (spec: orders need explicit confirmation before
    finalizing — see status transition endpoint below).
    """

    permission_classes = [IsStaffOrAbove]
    queryset = (
        Order.objects.select_related("customer", "confirmed_by").prefetch_related("items").all()
    )
    filterset_fields = ["status", "customer"]
    ordering_fields = ["created_at", "total_amount"]

    def get_serializer_class(self):
        return OrderCreateSerializer if self.request.method == "POST" else OrderSerializer

    def create(self, request, *args, **kwargs):
        # Overridden (not just perform_create) so the response can use
        # OrderSerializer's read-shaped `items` — OrderCreateSerializer's
        # own `items` field is write_only (it's the nested input), so
        # returning `serializer.data` directly would omit `items` entirely.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = self.perform_create(serializer)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def perform_create(self, serializer):
        items_data = serializer.validated_data.pop("items")
        order = serializer.save(tenant=self.request.user.tenant, status=Order.Status.PENDING)

        currency = order.currency
        for item in items_data:
            product = item["product"]
            currency = product.currency
            OrderItem.objects.create(
                tenant=order.tenant,
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=item["quantity"],
            )
        order.currency = currency
        order.save(update_fields=["currency", "updated_at"])
        order.recalculate_total()

        AuditLog.log(
            action="ORDER_CREATED",
            user=self.request.user,
            tenant=order.tenant,
            obj=order,
            metadata={"total_amount": str(order.total_amount), "item_count": len(items_data)},
        )
        return order


class OrderDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/orders/{id}/ — PATCH only touches `notes` (status has its own endpoint)."""

    permission_classes = [IsStaffOrAbove]
    serializer_class = OrderSerializer
    queryset = (
        Order.objects.select_related("customer", "confirmed_by").prefetch_related("items").all()
    )

    def perform_update(self, serializer):
        # `status` is read-only on OrderSerializer, so a PATCH here can
        # only ever change `notes` — status changes must go through
        # OrderStatusTransitionView, which validates the state machine.
        serializer.save()


class OrderStatusTransitionView(APIView):
    """
    POST /api/v1/orders/{id}/status/ {"status": "confirmed"}

    Validates the transition against Order.ALLOWED_TRANSITIONS — this is
    the only way to move an order out of PENDING, satisfying the spec's
    "require appropriate confirmation before finalizing an order."

    Note: this is a plain APIView, not a generics view, so
    core.mixins.TenantScopedQuerysetMixin (which assumes a
    GenericAPIView's `super().get_queryset()` chain) doesn't apply here —
    tenant scoping is done directly in get_queryset() below instead.
    """

    permission_classes = [IsStaffOrAbove]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Order.objects.all()
        return Order.objects.filter(tenant_id=user.tenant_id)

    def post(self, request, pk):
        order = generics.get_object_or_404(self.get_queryset(), pk=pk)
        serializer = UpdateOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        if not order.can_transition_to(new_status):
            raise ValidationError(f"Cannot move an order from '{order.status}' to '{new_status}'.")

        previous_status = order.status
        order.status = new_status
        update_fields = ["status", "updated_at"]
        if new_status == Order.Status.CONFIRMED:
            order.confirmed_by = request.user
            order.confirmed_at = timezone.now()
            update_fields += ["confirmed_by", "confirmed_at"]
        order.save(update_fields=update_fields)

        AuditLog.log(
            action="ORDER_STATUS_CHANGED",
            user=request.user,
            tenant=order.tenant,
            obj=order,
            metadata={"from": previous_status, "to": new_status},
        )

        return Response(OrderSerializer(order).data)
