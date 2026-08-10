"""WhatsAppBusinessAI — Products Serializers"""

from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    is_orderable = serializers.BooleanField(read_only=True)
    # Declared explicitly: DRF's ModelSerializer generates a UniqueValidator
    # for any field in a UniqueConstraint and — even though the model's
    # `blank=True` would normally make this optional — the *conditional*
    # constraint (`condition=~Q(sku="")`) confuses that inference into
    # `required=True`. The model's own constraint still enforces the real
    # uniqueness rule; this just fixes the field's optionality.
    sku = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "tenant",
            "name",
            "sku",
            "description",
            "category",
            "price",
            "currency",
            "stock",
            "is_available",
            "status",
            "is_orderable",
            "image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "is_orderable", "created_at", "updated_at"]
