"""
RAG knowledge base: extraction, chunking, the embed-or-degrade pipeline
(mocked HTTP for the success path; the no-API-key fallback is tested for
real since it's genuinely reachable without credentials), retrieval
(cosine similarity when embedded, keyword overlap otherwise), the
documents API, and its integration into apps.ai's system prompt.
"""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import post_save

from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.providers import get_embedding_provider
from apps.knowledge.services import (
    build_context_block,
    chunk_text,
    extract_text,
    process_document,
    retrieve_relevant_chunks,
    validate_file_extension,
)

from .conftest import auth_client


@pytest.fixture
def document_a(tenant_a):
    tenant, business, owner = tenant_a
    return KnowledgeDocument.objects.create(
        tenant=tenant,
        business=business,
        uploaded_by=owner,
        title="Return Policy",
        source_type=KnowledgeDocument.SourceType.TEXT,
        raw_text="Customers may return unopened items within 14 days of delivery for a full refund.",
    )


class TestChunkText:
    def test_short_text_is_a_single_chunk(self):
        assert chunk_text("hello world") == ["hello world"]

    def test_empty_text_produces_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_long_text_splits_with_overlap(self):
        words = [f"word{i}" for i in range(450)]
        text = " ".join(words)

        chunks = chunk_text(text)

        assert len(chunks) > 1
        # Every word from the source appears somewhere in the chunks.
        covered = set(" ".join(chunks).split())
        assert covered == set(words)
        # Consecutive chunks actually overlap (last words of chunk 0 reappear in chunk 1).
        assert chunks[0].split()[-1] in chunks[1].split()


class TestValidateFileExtension:
    def test_txt_and_pdf_allowed(self):
        validate_file_extension("policy.txt")
        validate_file_extension("policy.PDF")

    def test_other_extensions_rejected(self):
        with pytest.raises(ValidationError):
            validate_file_extension("policy.docx")
        with pytest.raises(ValidationError):
            validate_file_extension("policy.exe")


@pytest.mark.django_db
class TestExtractText:
    def test_text_source_returns_raw_text(self, document_a):
        assert extract_text(document_a) == document_a.raw_text

    def test_upload_txt_source_decodes_file(self, tenant_a):
        tenant, business, owner = tenant_a
        document = KnowledgeDocument.objects.create(
            tenant=tenant,
            business=business,
            uploaded_by=owner,
            title="FAQ",
            source_type=KnowledgeDocument.SourceType.UPLOAD,
            file=SimpleUploadedFile("faq.txt", b"We ship within 3 business days."),
        )

        assert extract_text(document) == "We ship within 3 business days."


@pytest.mark.django_db
class TestGetEmbeddingProvider:
    def test_none_without_api_key(self, settings):
        settings.OPENAI_API_KEY = ""
        assert get_embedding_provider() is None

    def test_configured_with_api_key(self, settings):
        settings.OPENAI_API_KEY = "sk-test"
        assert get_embedding_provider() is not None


@pytest.mark.django_db
class TestProcessDocument:
    def test_text_document_without_api_key_becomes_ready_unembedded(self, document_a, settings):
        settings.OPENAI_API_KEY = ""

        process_document(document_a)
        document_a.refresh_from_db()

        assert document_a.status == KnowledgeDocument.Status.READY
        assert document_a.chunk_count == 1
        assert document_a.embedded_chunk_count == 0
        chunk = document_a.chunks.get()
        assert chunk.embedding is None
        assert "14 days" in chunk.content

    def test_document_with_provider_gets_embedded(self, document_a, settings):
        settings.OPENAI_API_KEY = "sk-test"

        with patch("apps.knowledge.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.content = b"{}"
            mock_post.return_value.json.return_value = {
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]
            }
            process_document(document_a)

        document_a.refresh_from_db()
        assert document_a.status == KnowledgeDocument.Status.READY
        assert document_a.embedded_chunk_count == 1
        chunk = document_a.chunks.get()
        assert chunk.embedding == [0.1, 0.2, 0.3]
        assert chunk.embedding_model

    def test_empty_text_marks_document_failed(self, tenant_a):
        tenant, business, owner = tenant_a
        document = KnowledgeDocument.objects.create(
            tenant=tenant,
            business=business,
            uploaded_by=owner,
            title="Empty",
            source_type=KnowledgeDocument.SourceType.TEXT,
            raw_text="   ",
        )

        process_document(document)
        document.refresh_from_db()

        assert document.status == KnowledgeDocument.Status.FAILED
        assert document.error_message

    def test_reprocessing_replaces_old_chunks(self, document_a, settings):
        settings.OPENAI_API_KEY = ""
        process_document(document_a)
        assert document_a.chunks.count() == 1

        document_a.raw_text = "Updated policy: returns accepted within 30 days now."
        document_a.save()
        process_document(document_a)

        assert document_a.chunks.count() == 1
        assert "30 days" in document_a.chunks.get().content


@pytest.mark.django_db
class TestRetrieveRelevantChunks:
    def test_no_ready_documents_returns_empty(self, tenant_a):
        _, business, _ = tenant_a
        assert retrieve_relevant_chunks(business, "anything") == []

    def test_keyword_fallback_ranks_matching_chunk_first(self, tenant_a, document_a, settings):
        settings.OPENAI_API_KEY = ""
        process_document(document_a)  # -> 1 chunk about returns/refunds, unembedded

        tenant, business, owner = tenant_a
        other = KnowledgeDocument.objects.create(
            tenant=tenant,
            business=business,
            uploaded_by=owner,
            title="Hours",
            source_type=KnowledgeDocument.SourceType.TEXT,
            raw_text="We are open Monday to Saturday from 8am to 6pm.",
        )
        process_document(other)

        results = retrieve_relevant_chunks(business, "What is your refund policy?", top_k=2)

        assert results
        assert "refund" in results[0].content.lower()

    def test_no_matching_keywords_returns_empty(self, tenant_a, document_a, settings):
        settings.OPENAI_API_KEY = ""
        process_document(document_a)

        assert retrieve_relevant_chunks(tenant_a[1], "zzzzz qqqqq nomatch") == []

    def test_cosine_similarity_used_when_embedded(self, tenant_a, document_a, settings):
        settings.OPENAI_API_KEY = "sk-test"
        with patch("apps.knowledge.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.content = b"{}"
            mock_post.return_value.json.return_value = {
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}]
            }
            process_document(document_a)

        with patch("apps.knowledge.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.content = b"{}"
            mock_post.return_value.json.return_value = {
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}]
            }
            results = retrieve_relevant_chunks(
                tenant_a[1], "irrelevant text, matched by vector not words"
            )

        assert len(results) == 1


class TestBuildContextBlock:
    def test_empty_list_returns_empty_string(self):
        assert build_context_block([]) == ""

    def test_formats_chunk_content(self):
        chunk = KnowledgeChunk(chunk_index=0, content="Returns accepted within 14 days.")
        block = build_context_block([chunk])
        assert "Returns accepted within 14 days." in block
        assert "knowledge base" in block.lower()


@pytest.mark.django_db
class TestKnowledgeDocumentAPI:
    def test_manager_can_create_text_document_and_it_becomes_ready(
        self, api_client, tenant_a, settings
    ):
        settings.OPENAI_API_KEY = ""
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        business = tenant_a[1]

        resp = client.post(
            "/api/v1/knowledge/documents/",
            {
                "business": str(business.id),
                "title": "Shipping Policy",
                "source_type": "text",
                "raw_text": "We ship nationwide within 5 business days.",
            },
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert resp.data["status"] == "ready"  # Celery is eager in tests
        assert resp.data["chunk_count"] == 1
        assert "raw_text" not in resp.data

    def test_upload_requires_file(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        business = tenant_a[1]

        resp = client.post(
            "/api/v1/knowledge/documents/",
            {"business": str(business.id), "title": "Missing file", "source_type": "upload"},
            format="json",
        )

        assert resp.status_code == 400

    def test_upload_rejects_disallowed_extension(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        business = tenant_a[1]

        resp = client.post(
            "/api/v1/knowledge/documents/",
            {
                "business": str(business.id),
                "title": "Bad file",
                "source_type": "upload",
                "file": SimpleUploadedFile("policy.docx", b"not really a docx"),
            },
            format="multipart",
        )

        assert resp.status_code == 400

    def test_staff_cannot_create_document(self, api_client, tenant_a):
        from apps.accounts.models import User

        tenant, business, _ = tenant_a
        User.objects.create_user(
            email="staff-a@test.local",
            password="StaffSecret1!",
            first_name="Staff",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, "staff-a@test.local", "StaffSecret1!")

        resp = client.post(
            "/api/v1/knowledge/documents/",
            {"business": str(business.id), "title": "X", "source_type": "text", "raw_text": "x"},
            format="json",
        )

        assert resp.status_code == 403

    def test_staff_can_list_and_read_documents(self, api_client, tenant_a, document_a):
        from apps.accounts.models import User

        tenant, _, _ = tenant_a
        User.objects.create_user(
            email="staff-a@test.local",
            password="StaffSecret1!",
            first_name="Staff",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, "staff-a@test.local", "StaffSecret1!")

        resp = client.get("/api/v1/knowledge/documents/")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1

    def test_tenant_b_cannot_see_tenant_as_document(
        self, api_client, tenant_a, tenant_b, document_a
    ):
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_b.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/knowledge/documents/{document_a.id}/")
        assert resp.status_code == 404

    def test_cannot_create_document_for_another_tenants_business(
        self, api_client, tenant_a, tenant_b
    ):
        _, _, owner_a = tenant_a
        other_business = tenant_b[1]
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/knowledge/documents/",
            {
                "business": str(other_business.id),
                "title": "X",
                "source_type": "text",
                "raw_text": "x",
            },
            format="json",
        )

        assert resp.status_code == 400

    def test_manager_can_delete_document(self, api_client, tenant_a, document_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.delete(f"/api/v1/knowledge/documents/{document_a.id}/")

        assert resp.status_code == 204
        assert not KnowledgeDocument.objects.filter(id=document_a.id).exists()

    def test_chunks_endpoint_lists_indexed_chunks(
        self, api_client, tenant_a, document_a, settings
    ):
        settings.OPENAI_API_KEY = ""
        process_document(document_a)
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/knowledge/documents/{document_a.id}/chunks/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["is_embedded"] is False


@pytest.mark.django_db
class TestAIUsesKnowledgeBase:
    """
    CELERY_TASK_ALWAYS_EAGER=True means creating the inbound Message below
    would *also* synchronously fire apps.ai.signals.dispatch_ai_reply
    (real network call, unmocked, before our own direct call) unless
    disconnected first — same reasoning as tests/test_ai.py's
    TestGenerateAIReply._disconnect_signal.
    """

    @pytest.fixture(autouse=True)
    def _disconnect_ai_signal(self):
        from apps.ai.signals import dispatch_ai_reply
        from apps.messages.models import Message

        post_save.disconnect(dispatch_ai_reply, sender=Message)
        yield
        post_save.connect(dispatch_ai_reply, sender=Message)

    def test_reply_grounded_in_knowledge_base_chunk(self, tenant_a, settings):
        """Integration: generate_ai_reply's system prompt includes retrieved KB context."""
        from apps.ai.models import AISettings
        from apps.ai.services import generate_ai_reply
        from apps.conversations.models import Conversation
        from apps.customers.models import Customer
        from apps.messages.models import Message

        settings.OPENAI_API_KEY = "sk-test"
        tenant, business, _ = tenant_a
        AISettings.objects.create(tenant=tenant, business=business)

        doc = KnowledgeDocument.objects.create(
            tenant=tenant,
            business=business,
            title="Refunds",
            source_type=KnowledgeDocument.SourceType.TEXT,
            raw_text="Refunds are processed within 5 business days of the returned item arriving.",
        )
        process_document(doc)  # no API key mocked here -> unembedded, keyword-only

        customer = Customer.objects.create(tenant=tenant, name="C", phone="+254700009999")
        conversation = Conversation.objects.create(tenant=tenant, customer=customer)
        inbound = Message.objects.create(
            tenant=tenant,
            conversation=conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            content="How long do refunds take?",
            status=Message.Status.DELIVERED,
        )
        conversation.record_message(inbound)

        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["system_prompt"] = json["messages"][0]["content"]
            from unittest.mock import MagicMock

            response = MagicMock()
            response.status_code = 200
            response.content = b"{}"
            response.json.return_value = {
                "choices": [{"message": {"content": "5 business days."}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 5},
            }
            return response

        with patch("apps.ai.providers.requests.post", side_effect=fake_post):
            generate_ai_reply(inbound)

        assert "5 business days" in captured["system_prompt"]
