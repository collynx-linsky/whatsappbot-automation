"""WhatsAppBusinessAI — Knowledge Base Views"""

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.mixins import TenantScopedQuerysetMixin
from core.permissions import IsManagerOrAbove, IsStaffOrAbove

from .models import KnowledgeChunk, KnowledgeDocument
from .serializers import (
    KnowledgeChunkSerializer,
    KnowledgeDocumentCreateSerializer,
    KnowledgeDocumentSerializer,
)


class KnowledgeDocumentListCreateView(TenantScopedQuerysetMixin, generics.ListCreateAPIView):
    """
    GET /api/v1/knowledge/documents/ — staff+ (viewing the knowledge base
    is fine for anyone handling conversations).
    POST — manager+ (uploading/editing what the AI is grounded in is an
    admin action, same tier as connecting WhatsApp or changing AI settings).
    """

    queryset = KnowledgeDocument.objects.select_related("business", "uploaded_by").all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]

    def get_throttles(self):
        # Only POST (uploading -> real embedding-provider cost once a key
        # is configured) is scope-throttled — GET (listing/browsing the
        # knowledge base) shouldn't share that tight budget. See
        # docs/security.md.
        if self.request.method == "POST":
            self.throttle_scope = "knowledge_upload"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return KnowledgeDocumentCreateSerializer
        return KnowledgeDocumentSerializer

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if tenant is None:
            raise ValidationError(
                "A super admin has no tenant of their own and cannot create this directly."
            )
        serializer.save(tenant=tenant, uploaded_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        document = serializer.instance

        from .tasks import process_knowledge_document_task

        process_knowledge_document_task.delay(str(document.id))
        # CELERY_TASK_ALWAYS_EAGER in tests runs the task synchronously
        # above, mutating the DB row — but `document` is still the
        # pre-processing in-memory instance the task fetched its own copy
        # of, so it must be refreshed before we serialize it for the
        # response, or the caller sees a stale `status=pending`.
        document.refresh_from_db()

        from apps.common.models import AuditLog

        AuditLog.log(
            action="KNOWLEDGE_DOCUMENT_UPLOADED",
            user=request.user,
            tenant=document.tenant,
            obj=document,
            metadata={"title": document.title, "source_type": document.source_type},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        # Re-serialize with the read serializer so the response includes
        # status/chunk_count/etc — the create serializer's own `.data` is
        # write-only-blind on `raw_text` and lacks every server-computed
        # field (same reasoning as apps.orders' create() override).
        read_serializer = KnowledgeDocumentSerializer(
            document, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=201, headers=headers)


class KnowledgeDocumentDetailView(TenantScopedQuerysetMixin, generics.RetrieveDestroyAPIView):
    """GET (staff+) / DELETE (manager+) /api/v1/knowledge/documents/{id}/"""

    serializer_class = KnowledgeDocumentSerializer
    queryset = KnowledgeDocument.objects.select_related("business", "uploaded_by").all()

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class KnowledgeDocumentChunksView(generics.ListAPIView):
    """GET /api/v1/knowledge/documents/{id}/chunks/ — staff+, inspect what was actually indexed."""

    permission_classes = [IsStaffOrAbove]
    serializer_class = KnowledgeChunkSerializer

    def get_queryset(self):
        user = self.request.user
        documents = KnowledgeDocument.objects.all()
        if not user.is_superuser:
            documents = documents.filter(tenant_id=user.tenant_id)
        document = get_object_or_404(documents, pk=self.kwargs["pk"])
        return KnowledgeChunk.objects.filter(document=document)
