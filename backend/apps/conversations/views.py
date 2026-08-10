"""WhatsAppBusinessAI — Conversations Views"""

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.models import AuditLog
from core.mixins import TenantScopedCreateMixin, TenantScopedQuerysetMixin
from core.permissions import IsStaffOrAbove

from .models import Conversation, ConversationAssignment
from .serializers import ConversationAssignmentSerializer, ConversationSerializer


class ConversationListCreateView(
    TenantScopedQuerysetMixin, TenantScopedCreateMixin, generics.ListCreateAPIView
):
    """GET/POST /api/v1/conversations/"""

    permission_classes = [IsStaffOrAbove]
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.select_related("customer", "assigned_to").all()
    filterset_fields = ["status", "assigned_to", "ai_enabled"]
    search_fields = ["customer__name", "customer__phone"]
    ordering_fields = ["last_message_at", "created_at"]


class ConversationDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/conversations/{id}/"""

    permission_classes = [IsStaffOrAbove]
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.select_related("customer", "assigned_to").all()


class AssignConversationView(TenantScopedQuerysetMixin, APIView):
    """POST /api/v1/conversations/{id}/assign/ {"user_id": "<uuid>" | null}"""

    permission_classes = [IsStaffOrAbove]

    def get_queryset(self):
        return Conversation.objects.all()

    def post(self, request, pk):
        conversation = generics.get_object_or_404(self.get_queryset(), pk=pk)
        user_id = request.data.get("user_id")

        assignee = None
        if user_id:
            assignee = generics.get_object_or_404(
                User.objects.filter(tenant_id=request.user.tenant_id), pk=user_id
            )

        conversation.assign_to(assignee, assigned_by=request.user)
        AuditLog.log(
            action="CONVERSATION_ASSIGNED",
            user=request.user,
            tenant=conversation.tenant,
            obj=conversation,
            metadata={"assigned_to": str(assignee.id) if assignee else None},
        )
        return Response(ConversationSerializer(conversation).data)


class ConversationAssignmentHistoryView(generics.ListAPIView):
    """GET /api/v1/conversations/{id}/assignments/ — assignment history for one conversation."""

    permission_classes = [IsStaffOrAbove]
    serializer_class = ConversationAssignmentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ConversationAssignment.objects.filter(conversation_id=self.kwargs["pk"])
        if not user.is_superuser:
            qs = qs.filter(tenant_id=user.tenant_id)
        return qs
