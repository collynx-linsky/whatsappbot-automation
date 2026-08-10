"""WhatsAppBusinessAI — Knowledge Base Serializers"""

from rest_framework import serializers

from .models import KnowledgeChunk, KnowledgeDocument
from .services import validate_file_extension


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDocument
        fields = [
            "id",
            "tenant",
            "business",
            "title",
            "source_type",
            "file",
            "status",
            "error_message",
            "chunk_count",
            "embedded_chunk_count",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "status",
            "error_message",
            "chunk_count",
            "embedded_chunk_count",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]


class KnowledgeDocumentCreateSerializer(serializers.ModelSerializer):
    raw_text = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = ["id", "business", "title", "source_type", "file", "raw_text"]
        read_only_fields = ["id"]

    def validate_business(self, business):
        request = self.context["request"]
        if not request.user.is_superuser and business.tenant_id != request.user.tenant_id:
            raise serializers.ValidationError("Business not found.")
        return business

    def validate_file(self, file):
        if file is not None:
            validate_file_extension(file.name)
        return file

    def validate(self, attrs):
        source_type = attrs.get("source_type")
        if source_type == KnowledgeDocument.SourceType.UPLOAD and not attrs.get("file"):
            raise serializers.ValidationError({"file": "Required when source_type is 'upload'."})
        if (
            source_type == KnowledgeDocument.SourceType.TEXT
            and not attrs.get("raw_text", "").strip()
        ):
            raise serializers.ValidationError({"raw_text": "Required when source_type is 'text'."})
        return attrs


class KnowledgeChunkSerializer(serializers.ModelSerializer):
    is_embedded = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeChunk
        fields = ["id", "chunk_index", "content", "is_embedded", "created_at"]

    def get_is_embedded(self, obj):
        return bool(obj.embedding)
