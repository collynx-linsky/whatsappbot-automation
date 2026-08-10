"""WhatsAppBusinessAI — Conversations Serializers"""

from rest_framework import serializers

from .models import Conversation, ConversationAssignment


class ConversationSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Conversation
        fields = [
            "id",
            "tenant",
            "customer",
            "customer_name",
            "customer_phone",
            "channel",
            "status",
            "assigned_to",
            "assigned_to_name",
            "ai_enabled",
            "tags",
            "last_message_preview",
            "last_message_at",
            "unread_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "last_message_preview",
            "last_message_at",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def validate_customer(self, customer):
        """
        A conversation must belong to a customer in the *same* tenant as the
        caller — never trust that a client-supplied customer id already
        belongs to the right tenant, even though `tenant` itself is
        server-injected on create.
        """
        request = self.context["request"]
        if not request.user.is_superuser and customer.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Customer not found.")
        return customer

    def validate_assigned_to(self, user):
        if user is None:
            return user
        request = self.context["request"]
        if not request.user.is_superuser and user.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("User not found.")
        return user


class ConversationAssignmentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = ConversationAssignment
        fields = [
            "id",
            "conversation",
            "user",
            "user_name",
            "assigned_by",
            "assigned_at",
            "unassigned_at",
        ]
        read_only_fields = fields
