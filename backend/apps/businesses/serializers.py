"""WhatsAppBusinessAI — Businesses Serializers"""

from rest_framework import serializers

from .models import Business


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "id",
            "tenant",
            "name",
            "legal_name",
            "description",
            "category",
            "phone",
            "email",
            "website",
            "address",
            "city",
            "country",
            "timezone",
            "currency",
            "logo",
            "opening_hours",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]
