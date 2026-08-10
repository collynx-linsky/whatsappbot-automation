"""Conversations: CRUD, cross-tenant FK rejection, assignment, tenant isolation."""

import pytest

from apps.conversations.models import Conversation, ConversationAssignment

from .conftest import auth_client


@pytest.mark.django_db
class TestConversations:
    def test_staff_can_open_conversation_for_own_customer(self, api_client, tenant_a, customer_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/conversations/", {"customer": str(customer_a.id)}, format="json"
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["status"] == "open"
        assert resp.data["tenant"] == owner_a.tenant_id

    def test_cannot_open_conversation_for_another_tenants_customer(
        self, api_client, tenant_a, customer_b
    ):
        """The classic cross-tenant-FK trick: pass a real id, just from the wrong tenant."""
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/conversations/", {"customer": str(customer_b.id)}, format="json"
        )
        assert resp.status_code == 400

    def test_owner_cannot_read_other_tenants_conversation(
        self, api_client, tenant_a, tenant_b, customer_b
    ):
        _, _, owner_a = tenant_a
        tenant_b_obj, _, _ = tenant_b
        conversation_b = Conversation.objects.create(tenant=tenant_b_obj, customer=customer_b)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/conversations/{conversation_b.id}/")
        assert resp.status_code == 404

    def test_assign_conversation_logs_history(self, api_client, tenant_a, customer_a):
        tenant_a_obj, _, owner_a = tenant_a
        conversation = Conversation.objects.create(tenant=tenant_a_obj, customer=customer_a)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            f"/api/v1/conversations/{conversation.id}/assign/",
            {"user_id": str(owner_a.id)},
            format="json",
        )
        assert resp.status_code == 200
        conversation.refresh_from_db()
        assert conversation.assigned_to_id == owner_a.id
        assert ConversationAssignment.objects.filter(
            conversation=conversation, user=owner_a
        ).exists()

    def test_cannot_assign_to_a_user_from_another_tenant(
        self, api_client, tenant_a, tenant_b, customer_a
    ):
        tenant_a_obj, _, owner_a = tenant_a
        _, _, owner_b = tenant_b
        conversation = Conversation.objects.create(tenant=tenant_a_obj, customer=customer_a)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            f"/api/v1/conversations/{conversation.id}/assign/",
            {"user_id": str(owner_b.id)},
            format="json",
        )
        assert resp.status_code == 404
