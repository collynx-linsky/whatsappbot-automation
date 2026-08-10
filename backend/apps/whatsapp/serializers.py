"""WhatsAppBusinessAI — WhatsApp Serializers"""

from rest_framework import serializers

from .models import WhatsAppAccount


class WhatsAppAccountSerializer(serializers.ModelSerializer):
    """
    `access_token` is write-only — accepted on create/update, encrypted
    immediately via the model's property setter, and NEVER included in any
    response. There is deliberately no field that exposes it, masked or
    otherwise, per spec section 25 ("Never expose sensitive credentials
    through APIs").
    """

    access_token = serializers.CharField(write_only=True, required=True, trim_whitespace=True)
    is_connected = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppAccount
        fields = [
            "id",
            "tenant",
            "business",
            "display_name",
            "phone_number",
            "phone_number_id",
            "business_account_id",
            "access_token",
            "status",
            "is_connected",
            "connected_at",
            "last_sync_at",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "status",
            "connected_at",
            "last_sync_at",
            "last_error",
            "created_at",
            "updated_at",
        ]

    def get_is_connected(self, obj) -> bool:
        return obj.status == WhatsAppAccount.Status.CONNECTED

    def validate_business(self, business):
        request = self.context["request"]
        if not request.user.is_superuser and business.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Business not found.")
        return business

    def create(self, validated_data):
        token = validated_data.pop("access_token")
        account = WhatsAppAccount(**validated_data)
        account.access_token = token
        account.save()
        # No live handshake with Meta is performed here (no "test the
        # token" call) — accepted credentials are optimistically marked
        # connected. A future refinement could call the Graph API to
        # confirm the phone number before flipping this.
        account.mark_connected()
        return account

    def update(self, instance, validated_data):
        token = validated_data.pop("access_token", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if token:
            instance.access_token = token
        instance.save()
        return instance
