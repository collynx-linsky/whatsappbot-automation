"""WhatsAppBusinessAI — Messages Serializers"""

from rest_framework import serializers

from .models import Message, MessageAttachment


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ["id", "message", "file", "file_name", "file_type", "file_size", "created_at"]
        read_only_fields = ["id", "message", "created_at"]


class MessageSerializer(serializers.ModelSerializer):
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Message
        fields = [
            "id",
            "tenant",
            "conversation",
            "sender_type",
            "sender_user",
            "sender_name",
            "direction",
            "message_type",
            "content",
            "status",
            "external_message_id",
            "attachments",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "sender_user",
            "sender_name",
            "direction",
            "status",
            "external_message_id",
            "attachments",
            "created_at",
        ]

    def validate_conversation(self, conversation):
        request = self.context["request"]
        if not request.user.is_superuser and conversation.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Conversation not found.")
        return conversation

    def validate_sender_type(self, sender_type):
        """
        This phase has no real WhatsApp/AI integration yet (Phase 7/8), so
        this endpoint is the manual/testing surface for creating messages.
        Only STAFF is meaningful to create via the API right now — CUSTOMER
        messages arrive via the webhook (not built), and AI/SYSTEM messages
        are generated server-side, not posted by a client.
        """
        if sender_type != Message.SenderType.STAFF:
            raise serializers.ValidationError(
                "Only staff-authored messages can be created via this endpoint "
                "in this phase — customer/AI messages arrive via the (not yet "
                "built) WhatsApp webhook and AI engine."
            )
        return sender_type
