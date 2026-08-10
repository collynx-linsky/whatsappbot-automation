"""WhatsAppBusinessAI — AI Serializers"""

from rest_framework import serializers

from .models import AISettings


class AISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISettings
        fields = [
            "id",
            "tenant",
            "business",
            "assistant_name",
            "system_prompt",
            "language",
            "tone",
            "welcome_message",
            "fallback_message",
            "max_response_length",
            "mode",
            "ai_enabled",
            "human_handoff_enabled",
            "confidence_threshold",
            "handoff_keywords",
            "provider",
            "model_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]

    def validate_business(self, business):
        request = self.context["request"]
        if not request.user.is_superuser and business.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Business not found.")
        return business


class AITestSerializer(serializers.Serializer):
    """POST /api/v1/ai/test/ — try the assistant without a real conversation (onboarding step 7)."""

    message = serializers.CharField(max_length=2000)


class AITestResponseSerializer(serializers.Serializer):
    handed_off = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_null=True)
    reply = serializers.CharField(required=False, allow_null=True)
    confidence = serializers.FloatField(required=False, allow_null=True)
