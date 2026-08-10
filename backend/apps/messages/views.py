"""WhatsAppBusinessAI — Messages Views"""

from rest_framework import generics

from core.mixins import TenantScopedQuerysetMixin
from core.permissions import IsStaffOrAbove

from .models import Message
from .serializers import MessageSerializer


class MessageListCreateView(TenantScopedQuerysetMixin, generics.ListCreateAPIView):
    """
    GET /api/v1/messages/?conversation=<uuid> — list messages (newest last).
    POST /api/v1/messages/ — post a staff reply into a conversation.
    """

    permission_classes = [IsStaffOrAbove]
    serializer_class = MessageSerializer
    queryset = Message.objects.select_related("sender_user").prefetch_related("attachments").all()
    filterset_fields = ["conversation", "sender_type", "direction"]
    ordering_fields = ["created_at"]

    def perform_create(self, serializer):
        conversation = serializer.validated_data["conversation"]
        message = serializer.save(
            tenant=self.request.user.tenant,
            sender_user=self.request.user,
            direction=Message.Direction.OUTBOUND,
            status=Message.Status.SENT,
        )
        conversation.record_message(message)


class MessageDetailView(TenantScopedQuerysetMixin, generics.RetrieveAPIView):
    """GET /api/v1/messages/{id}/"""

    permission_classes = [IsStaffOrAbove]
    serializer_class = MessageSerializer
    queryset = Message.objects.select_related("sender_user").prefetch_related("attachments").all()
