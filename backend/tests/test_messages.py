"""Messages: creation updates the conversation preview, cross-tenant rejection, isolation."""

import pytest

from apps.conversations.models import Conversation
from apps.messages.models import Message

from .conftest import auth_client


@pytest.mark.django_db
class TestMessages:
    def test_staff_can_post_message_and_conversation_preview_updates(
        self, api_client, tenant_a, customer_a
    ):
        tenant_a_obj, _, owner_a = tenant_a
        conversation = Conversation.objects.create(tenant=tenant_a_obj, customer=customer_a)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/messages/",
            {
                "conversation": str(conversation.id),
                "sender_type": "staff",
                "content": "Hello there!",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["direction"] == "outbound"
        assert resp.data["sender_name"] == owner_a.get_full_name()

        conversation.refresh_from_db()
        assert conversation.last_message_preview == "Hello there!"
        assert conversation.last_message_at is not None

    def test_only_staff_sender_type_accepted_this_phase(self, api_client, tenant_a, customer_a):
        tenant_a_obj, _, owner_a = tenant_a
        conversation = Conversation.objects.create(tenant=tenant_a_obj, customer=customer_a)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/messages/",
            {"conversation": str(conversation.id), "sender_type": "customer", "content": "hi"},
            format="json",
        )
        assert resp.status_code == 400

    def test_cannot_post_message_into_another_tenants_conversation(
        self, api_client, tenant_a, tenant_b, customer_b
    ):
        _, _, owner_a = tenant_a
        tenant_b_obj, _, _ = tenant_b
        conversation_b = Conversation.objects.create(tenant=tenant_b_obj, customer=customer_b)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/messages/",
            {"conversation": str(conversation_b.id), "sender_type": "staff", "content": "sneaky"},
            format="json",
        )
        assert resp.status_code == 400
        assert not Message.objects.filter(content="sneaky").exists()

    def test_owner_only_lists_own_tenant_messages(
        self, api_client, tenant_a, tenant_b, customer_a, customer_b
    ):
        tenant_a_obj, _, owner_a = tenant_a
        tenant_b_obj, _, _ = tenant_b
        conversation_a = Conversation.objects.create(tenant=tenant_a_obj, customer=customer_a)
        conversation_b = Conversation.objects.create(tenant=tenant_b_obj, customer=customer_b)
        msg_a = Message.objects.create(
            tenant=tenant_a_obj,
            conversation=conversation_a,
            sender_type="staff",
            direction="outbound",
            content="A's message",
        )
        Message.objects.create(
            tenant=tenant_b_obj,
            conversation=conversation_b,
            sender_type="staff",
            direction="outbound",
            content="B's message",
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/messages/")
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.data["results"]]
        assert str(msg_a.id) in ids
        assert len(ids) == 1
