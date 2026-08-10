"""
AI engine: settings CRUD + tenant isolation, provider selection without
credentials, handoff-keyword detection, the full generate_ai_reply
orchestrator (provider HTTP mocked for success paths; the no-API-key path
is tested for real since it's genuinely reachable without credentials),
and the /ai/test/ onboarding endpoint.
"""

from unittest.mock import patch

import pytest
from django.db.models.signals import post_save

from apps.ai.models import AISettings
from apps.ai.providers import AnthropicProvider, OpenAIProvider, get_provider
from apps.ai.services import generate_ai_reply, wants_human
from apps.ai.signals import dispatch_ai_reply
from apps.businesses.models import Business
from apps.conversations.models import Conversation
from apps.messages.models import Message

from .conftest import auth_client


@pytest.fixture
def ai_settings_a(tenant_a):
    tenant, _, _ = tenant_a
    business = Business.objects.get(tenant=tenant)
    return AISettings.objects.create(tenant=tenant, business=business)


@pytest.fixture
def conversation_a(tenant_a, customer_a):
    tenant, _, _ = tenant_a
    return Conversation.objects.create(tenant=tenant, customer=customer_a)


def _inbound(conversation, tenant, text="Hello, how much is the blue shirt?"):
    message = Message.objects.create(
        tenant=tenant,
        conversation=conversation,
        sender_type=Message.SenderType.CUSTOMER,
        direction=Message.Direction.INBOUND,
        content=text,
        status=Message.Status.DELIVERED,
    )
    conversation.record_message(message)
    return message


class TestGetProvider:
    def test_returns_none_without_api_key(self, settings):
        settings.OPENAI_API_KEY = ""
        settings.ANTHROPIC_API_KEY = ""
        assert get_provider("openai") is None
        assert get_provider("anthropic") is None

    def test_returns_configured_instance_with_api_key(self, settings):
        settings.OPENAI_API_KEY = "sk-test"
        settings.ANTHROPIC_API_KEY = "sk-ant-test"
        assert isinstance(get_provider("openai"), OpenAIProvider)
        assert isinstance(get_provider("anthropic"), AnthropicProvider)

    def test_unknown_provider_returns_none(self):
        assert get_provider("does-not-exist") is None


class TestWantsHuman:
    def test_builtin_phrase_matches(self):
        assert wants_human("please let me talk to a human", []) is not None

    def test_custom_keyword_matches_case_insensitively(self):
        assert wants_human("I want a REFUND now", ["refund"]) is not None

    def test_ordinary_message_does_not_match(self):
        assert wants_human("What time do you open tomorrow?", ["refund"]) is None


@pytest.mark.django_db
class TestGenerateAIReply:
    """
    These tests call generate_ai_reply() directly to control exactly what
    it sees. CELERY_TASK_ALWAYS_EAGER=True (config/settings/test.py) means
    apps.ai.signals.dispatch_ai_reply would otherwise *also* run it
    synchronously the moment _inbound() creates the customer message —
    double-invoking it and corrupting conversation.ai_enabled before our
    own call even happens. Disconnect it for this class only.
    """

    @pytest.fixture(autouse=True)
    def _disconnect_signal(self):
        post_save.disconnect(dispatch_ai_reply, sender=Message)
        yield
        post_save.connect(dispatch_ai_reply, sender=Message)

    def test_no_api_key_hands_off_gracefully(self, ai_settings_a, conversation_a, tenant_a):
        tenant, _, _ = tenant_a
        inbound = _inbound(conversation_a, tenant)

        reply = generate_ai_reply(inbound)

        assert reply is not None
        assert reply.sender_type == Message.SenderType.AI
        assert reply.content == ai_settings_a.fallback_message
        conversation_a.refresh_from_db()
        assert conversation_a.ai_enabled is False

    def test_no_api_key_and_handoff_disabled_sends_nothing(
        self, ai_settings_a, conversation_a, tenant_a
    ):
        ai_settings_a.human_handoff_enabled = False
        ai_settings_a.save()
        tenant, _, _ = tenant_a
        inbound = _inbound(conversation_a, tenant)

        assert generate_ai_reply(inbound) is None
        conversation_a.refresh_from_db()
        assert conversation_a.ai_enabled is True

    def test_human_only_mode_never_replies(self, ai_settings_a, conversation_a, tenant_a):
        ai_settings_a.mode = AISettings.Mode.HUMAN
        ai_settings_a.save()
        tenant, _, _ = tenant_a
        inbound = _inbound(conversation_a, tenant)

        assert generate_ai_reply(inbound) is None

    def test_handoff_keyword_bypasses_provider_call(self, ai_settings_a, conversation_a, tenant_a):
        ai_settings_a.handoff_keywords = ["refund"]
        ai_settings_a.save()
        tenant, _, _ = tenant_a
        inbound = _inbound(conversation_a, tenant, text="I need a refund please")

        with patch("apps.ai.providers.requests.post") as mock_post:
            reply = generate_ai_reply(inbound)

        mock_post.assert_not_called()
        assert reply.sender_type == Message.SenderType.AI
        assert reply.content == ai_settings_a.fallback_message

    def test_successful_provider_reply_is_sent(
        self, ai_settings_a, conversation_a, tenant_a, settings
    ):
        settings.OPENAI_API_KEY = "sk-test"
        tenant, _, _ = tenant_a
        inbound = _inbound(conversation_a, tenant)

        with patch("apps.ai.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.content = b"{}"
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "It's KES 1500."}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 42},
            }
            reply = generate_ai_reply(inbound)

        assert reply.sender_type == Message.SenderType.AI
        assert reply.content == "It's KES 1500."
        conversation_a.refresh_from_db()
        assert conversation_a.ai_enabled is True

    def test_low_confidence_reply_hands_off(
        self, ai_settings_a, conversation_a, tenant_a, settings
    ):
        settings.OPENAI_API_KEY = "sk-test"
        tenant, _, _ = tenant_a
        inbound = _inbound(conversation_a, tenant)

        with patch("apps.ai.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.content = b"{}"
            mock_post.return_value.json.return_value = {
                "choices": [
                    {"message": {"content": "I'm not sure about that."}, "finish_reason": "stop"}
                ],
                "usage": {"total_tokens": 10},
            }
            reply = generate_ai_reply(inbound)

        assert reply.content == ai_settings_a.fallback_message
        conversation_a.refresh_from_db()
        assert conversation_a.ai_enabled is False

    def test_ai_disabled_globally_returns_none(self, ai_settings_a, conversation_a, tenant_a):
        ai_settings_a.ai_enabled = False
        ai_settings_a.save()
        tenant, _, _ = tenant_a
        assert generate_ai_reply(_inbound(conversation_a, tenant)) is None

    def test_ai_disabled_on_conversation_returns_none(
        self, ai_settings_a, conversation_a, tenant_a
    ):
        conversation_a.ai_enabled = False
        conversation_a.save()
        tenant, _, _ = tenant_a
        assert generate_ai_reply(_inbound(conversation_a, tenant)) is None


@pytest.mark.django_db
class TestAISettingsAPI:
    def test_owner_can_get_settings_created_lazily(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/ai/settings/")

        assert resp.status_code == 200, resp.data
        assert resp.data["mode"] == AISettings.Mode.HYBRID
        assert AISettings.objects.count() == 1

    def test_owner_can_update_settings(self, api_client, tenant_a, ai_settings_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            "/api/v1/ai/settings/",
            {"assistant_name": "Amina", "handoff_keywords": ["complaint"]},
            format="json",
        )

        assert resp.status_code == 200, resp.data
        ai_settings_a.refresh_from_db()
        assert ai_settings_a.assistant_name == "Amina"
        assert ai_settings_a.handoff_keywords == ["complaint"]

    def test_tenant_b_gets_own_settings_not_tenant_as(
        self, api_client, tenant_a, tenant_b, ai_settings_a
    ):
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_b.email, "OwnerSecret1!")

        resp = client.get("/api/v1/ai/settings/")

        assert resp.status_code == 200, resp.data
        # tenant_b gets its OWN lazily-created settings, never tenant_a's.
        assert resp.data["id"] != str(ai_settings_a.id)
        assert AISettings.objects.count() == 2

    def test_staff_cannot_update_settings(self, api_client, tenant_a, ai_settings_a):
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

        resp = client.patch("/api/v1/ai/settings/", {"assistant_name": "X"}, format="json")

        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get("/api/v1/ai/settings/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestAITestEndpoint:
    def test_no_api_key_reports_handed_off(self, api_client, tenant_a, ai_settings_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post("/api/v1/ai/test/", {"message": "Hi there"}, format="json")

        assert resp.status_code == 200, resp.data
        assert resp.data["handed_off"] is True

    def test_handoff_keyword_short_circuits(self, api_client, tenant_a, ai_settings_a):
        ai_settings_a.handoff_keywords = ["refund"]
        ai_settings_a.save()
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        with patch("apps.ai.providers.requests.post") as mock_post:
            resp = client.post("/api/v1/ai/test/", {"message": "I want a refund"}, format="json")

        mock_post.assert_not_called()
        assert resp.data["handed_off"] is True
        assert "refund" in resp.data["reason"]

    def test_successful_reply_returned(self, api_client, tenant_a, ai_settings_a, settings):
        settings.OPENAI_API_KEY = "sk-test"
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        with patch("apps.ai.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.content = b"{}"
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "We open at 8am."}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 12},
            }
            resp = client.post(
                "/api/v1/ai/test/", {"message": "What time do you open?"}, format="json"
            )

        assert resp.status_code == 200, resp.data
        assert resp.data["handed_off"] is False
        assert resp.data["reply"] == "We open at 8am."
