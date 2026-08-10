"""WhatsAppBusinessAI — Orders Serializers"""

from rest_framework import serializers

from apps.products.models import Product

from .models import Order, OrderItem


class OrderItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "unit_price", "quantity", "subtotal"]
        read_only_fields = fields


class OrderItemWriteSerializer(serializers.Serializer):
    """Client only supplies `product` + `quantity` — price/name are snapshotted server-side."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    confirmed_by_name = serializers.CharField(
        source="confirmed_by.get_full_name", read_only=True, default=None
    )
    items = OrderItemReadSerializer(many=True, read_only=True)
    # Write-only nested input — not the same field as the read-only `items`
    # above; DRF resolves same-name read/write pairs awkwardly, so this one
    # is named distinctly and mapped in the view instead of Meta.fields.

    class Meta:
        model = Order
        fields = [
            "id",
            "tenant",
            "customer",
            "customer_name",
            "customer_phone",
            "conversation",
            "status",
            "total_amount",
            "currency",
            "notes",
            "confirmed_by",
            "confirmed_by_name",
            "confirmed_at",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "status",
            "total_amount",
            "confirmed_by",
            "confirmed_at",
            "items",
            "created_at",
            "updated_at",
        ]

    def validate_customer(self, customer):
        request = self.context["request"]
        if not request.user.is_superuser and customer.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Customer not found.")
        return customer

    def validate_conversation(self, conversation):
        if conversation is None:
            return conversation
        request = self.context["request"]
        if not request.user.is_superuser and conversation.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Conversation not found.")
        return conversation


class OrderCreateSerializer(OrderSerializer):
    """Adds the write-only nested `items` input used only on create."""

    items = OrderItemWriteSerializer(many=True, write_only=True)

    class Meta(OrderSerializer.Meta):
        read_only_fields = [f for f in OrderSerializer.Meta.read_only_fields if f != "items"]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("An order must have at least one item.")
        request = self.context["request"]
        for item in items:
            product = item["product"]
            if not request.user.is_superuser and product.tenant_id != request.user.tenant_id:
                raise serializers.ValidationError("One or more products were not found.")
        return items


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
