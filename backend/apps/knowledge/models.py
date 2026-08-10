"""
WhatsAppBusinessAI — RAG Knowledge Base Models (spec section 9)

    KnowledgeDocument   one row per uploaded file / pasted text block
        |
        `-- KnowledgeChunk[]   the document split into retrieval-sized
                                pieces, each with (or without — see
                                docs/rag.md) a real embedding vector

Retrieval reads `KnowledgeChunk`, never `KnowledgeDocument.raw_text`
directly — chunking exists so a reply only pulls in the few paragraphs
actually relevant to the customer's question, not an entire document.
"""

from django.db import models

from core.models import BaseModel


class KnowledgeDocument(BaseModel):
    class SourceType(models.TextChoices):
        UPLOAD = "upload", "Uploaded file"
        TEXT = "text", "Pasted text"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="knowledge_documents"
    )
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    title = models.CharField(max_length=255)
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    file = models.FileField(upload_to="knowledge/documents/%Y/%m/", null=True, blank=True)
    raw_text = models.TextField(
        blank=True,
        help_text=(
            "For source_type=text, the pasted content itself. For "
            "source_type=upload, the text extracted from `file` once "
            "processing succeeds."
        ),
    )

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    embedded_chunk_count = models.PositiveIntegerField(
        default=0,
        help_text=(
            "How many chunks got a real embedding vector, vs. falling back "
            "to keyword-only retrieval because no embedding provider API "
            "key was configured at process time — see docs/rag.md."
        ),
    )

    class Meta:
        db_table = "knowledge_document"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "business"])]

    def __str__(self):
        return f"{self.title} ({self.business.name})"


class KnowledgeChunk(BaseModel):
    document = models.ForeignKey(
        KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()

    # No pgvector extension on this project's native Postgres instance (not
    # installed at the OS level — `CREATE EXTENSION` alone can't add it) so
    # embeddings are a plain JSON float list, and retrieval falls back to
    # pure-Python cosine similarity rather than a vector index. Fine at the
    # per-business knowledge base scale this MVP targets (dozens–hundreds of
    # chunks); see docs/rag.md for the documented upgrade path.
    embedding = models.JSONField(null=True, blank=True)
    embedding_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Blank if this chunk was never successfully embedded.",
    )

    class Meta:
        db_table = "knowledge_chunk"
        ordering = ["document", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"], name="unique_chunk_index_per_document"
            )
        ]
        indexes = [models.Index(fields=["tenant", "document"])]

    def __str__(self):
        return f"{self.document.title} chunk {self.chunk_index}"
