"""WhatsAppBusinessAI — Campaigns Serializers"""

from rest_framework import serializers

from .models import Campaign, CampaignRecipient, MessageTemplate, Segment
from .services import get_segment_customers


def _validate_business(business, request):
    if not request.user.is_superuser and business.tenant_id != request.user.tenant_id:
        raise serializers.ValidationError("Business not found.")
    return business


class MessageTemplateSerializer(serializers.ModelSerializer):
    variable_count = serializers.ReadOnlyField()

    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "tenant",
            "business",
            "created_by",
            "name",
            "whatsapp_template_name",
            "category",
            "language_code",
            "body_text",
            "status",
            "rejection_reason",
            "variable_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_by", "created_at", "updated_at"]

    def validate_business(self, business):
        return _validate_business(business, self.context["request"])


class SegmentSerializer(serializers.ModelSerializer):
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = Segment
        fields = [
            "id",
            "tenant",
            "business",
            "created_by",
            "name",
            "description",
            "filters",
            "customer_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_by", "created_at", "updated_at"]

    def validate_business(self, business):
        return _validate_business(business, self.context["request"])

    def validate_filters(self, filters):
        allowed_keys = {"statuses", "sources", "tags"}
        unknown = set(filters) - allowed_keys
        if unknown:
            raise serializers.ValidationError(f"Unsupported filter key(s): {', '.join(unknown)}.")
        return filters

    def get_customer_count(self, obj):
        return get_segment_customers(obj).count()


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            "id",
            "tenant",
            "business",
            "segment",
            "template",
            "created_by",
            "name",
            "template_variables",
            "status",
            "scheduled_at",
            "started_at",
            "completed_at",
            "error_message",
            "recipient_count",
            "sent_count",
            "failed_count",
            "skipped_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "created_by",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "recipient_count",
            "sent_count",
            "failed_count",
            "skipped_count",
            "created_at",
            "updated_at",
        ]

    def validate_business(self, business):
        return _validate_business(business, self.context["request"])

    def validate(self, attrs):
        business = attrs.get("business") or getattr(self.instance, "business", None)
        segment = attrs.get("segment") or getattr(self.instance, "segment", None)
        template = attrs.get("template") or getattr(self.instance, "template", None)
        if segment is not None and business is not None and segment.business_id != business.id:
            raise serializers.ValidationError(
                {"segment": "Segment belongs to a different business."}
            )
        if template is not None and business is not None and template.business_id != business.id:
            raise serializers.ValidationError(
                {"template": "Template belongs to a different business."}
            )
        return attrs


class CampaignRecipientSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)

    class Meta:
        model = CampaignRecipient
        fields = [
            "id",
            "customer",
            "customer_name",
            "customer_phone",
            "status",
            "skip_reason",
            "error_message",
            "sent_at",
            "created_at",
        ]


class SegmentPreviewSerializer(serializers.Serializer):
    customer_count = serializers.IntegerField()
    sample = serializers.ListField(child=serializers.DictField())
