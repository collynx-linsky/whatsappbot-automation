"""WhatsAppBusinessAI — Billing Serializers"""

from rest_framework import serializers

from apps.tenants.models import Tenant

from .models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            "id",
            "tenant",
            "invoice_number",
            "period_start",
            "period_end",
            "plan_name",
            "amount",
            "currency",
            "status",
            "issued_at",
            "due_at",
            "paid_at",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class GenerateInvoiceSerializer(serializers.Serializer):
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all())
    period_start = serializers.DateField(required=False)
