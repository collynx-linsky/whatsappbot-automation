from django.contrib import admin

from .models import KnowledgeChunk, KnowledgeDocument


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    fields = ["chunk_index", "content", "embedding_model"]
    readonly_fields = ["chunk_index", "content", "embedding_model"]
    can_delete = False


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "business",
        "tenant",
        "source_type",
        "status",
        "chunk_count",
        "embedded_chunk_count",
    ]
    list_filter = ["status", "source_type", "tenant"]
    search_fields = ["title", "business__name"]
    readonly_fields = ["chunk_count", "embedded_chunk_count", "error_message"]
    inlines = [KnowledgeChunkInline]
