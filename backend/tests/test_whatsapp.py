"""
WhatsApp integration: signature verification, webhook idempotency, tenant
resolution via phone_number_id, account CRUD (token never exposed),
encryption round-trip, and the outbound-send Celery task (HTTP mocked).
"""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.conversations.models import Conversation
from apps.customers.models import Customer
from apps.messages.models import Message
from apps.whatsapp.models import MessageEvent, WhatsAppAccount
from core.crypto import decrypt_secret, encrypt_secret

from .conftest import auth_client

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"


def _sign(body: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _sample_payload(
    phone_number_id="123456", wa_id="254700999001", message_id="wamid.TEST1", text="Hello!"
):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+254700000000",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"profile": {"name": "Test Contact"}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture(autouse=True)
def whatsapp_settings(settings):
    settings.WHATSAPP_APP_SECRET = APP_SECRET
    settings.WHATSAPP_VERIFY_TOKEN = VERIFY_TOKEN
    # core.crypto reads FIELD_ENCRYPTION_KEY (not WHATSAPP_TOKEN_ENCRYPTION_KEY
    # directly) — see core/crypto.py's generalization note.
    settings.FIELD_ENCRYPTION_KEY = "u_aeZR2Zfksak3SwNr-u-kzLvYRTIhDnd2HMd1dFqZM="


@pytest.fixture
def whatsapp_account(tenant_a):
    from apps.businesses.models import Business

    tenant, _, _ = tenant_a
    business = Business.objects.get(tenant=tenant)
    account = WhatsAppAccount(
        tenant=tenant,
        business=business,
        phone_number="+254700000000",
        phone_number_id="123456",
        business_account_id="WABA_ID",
    )
    account.access_token = "real-plaintext-token"
    account.save()
    account.mark_connected()  # constructed directly, not via the API serializer — do what it would have
    return account


class TestEncryption:
    def test_round_trip(self):
        token = encrypt_secret("super-secret-value")
        assert token != "super-secret-value"
        assert decrypt_secret(token) == "super-secret-value"

    def test_account_access_token_encrypted_at_rest(self, whatsapp_account):
        assert whatsapp_account.access_token_encrypted != "real-plaintext-token"
        assert whatsapp_account.access_token == "real-plaintext-token"


@pytest.mark.django_db
class TestWebhookVerification:
    def test_get_with_correct_token_returns_challenge(self, api_client):
        url = reverse("whatsapp:webhook")
        resp = api_client.get(
            url,
            {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "123abc"},
        )
        assert resp.status_code == 200
        assert resp.content.decode() == "123abc"

    def test_get_with_wrong_token_rejected(self, api_client):
        url = reverse("whatsapp:webhook")
        resp = api_client.get(
            url, {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123abc"}
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestWebhookSignature:
    def test_post_without_signature_rejected(self, whatsapp_account):
        client = Client()
        body = json.dumps(_sample_payload()).encode()
        resp = client.generic(
            "POST", reverse("whatsapp:webhook"), data=body, content_type="application/json"
        )
        assert resp.status_code == 403
        assert not Message.objects.exists()

    def test_post_with_wrong_signature_rejected(self, whatsapp_account):
        client = Client()
        body = json.dumps(_sample_payload()).encode()
        resp = client.generic(
            "POST",
            reverse("whatsapp:webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=" + "0" * 64,
        )
        assert resp.status_code == 403
        assert not Message.objects.exists()

    def test_post_with_valid_signature_accepted(self, whatsapp_account):
        client = Client()
        body = json.dumps(_sample_payload()).encode()
        resp = client.generic(
            "POST",
            reverse("whatsapp:webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
        )
        assert resp.status_code == 200
        assert resp.json()["created"] == 1


@pytest.mark.django_db
class TestWebhookProcessing:
    def _post(self, payload):
        client = Client()
        body = json.dumps(payload).encode()
        return client.generic(
            "POST",
            reverse("whatsapp:webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
        )

    def test_inbound_message_creates_customer_conversation_message_in_right_tenant(
        self, whatsapp_account
    ):
        tenant = whatsapp_account.tenant
        resp = self._post(_sample_payload())
        assert resp.status_code == 200

        customer = Customer.objects.get(tenant=tenant, phone="254700999001")
        assert customer.name == "Test Contact"
        conversation = Conversation.objects.get(tenant=tenant, customer=customer)
        message = Message.objects.get(tenant=tenant, conversation=conversation)
        assert message.direction == Message.Direction.INBOUND
        assert message.sender_type == Message.SenderType.CUSTOMER
        assert message.content == "Hello!"
        assert message.external_message_id == "wamid.TEST1"

    def test_duplicate_delivery_is_idempotent(self, whatsapp_account):
        payload = _sample_payload(message_id="wamid.DUPLICATE")
        self._post(payload)
        self._post(payload)  # Meta redelivers the exact same event

        assert Message.objects.filter(external_message_id="wamid.DUPLICATE").count() == 1
        assert MessageEvent.objects.filter(external_event_id="wamid.DUPLICATE").count() == 1

    def test_unknown_phone_number_id_is_ignored_not_crashed(self, whatsapp_account):
        resp = self._post(_sample_payload(phone_number_id="does-not-exist"))
        assert resp.status_code == 200
        assert resp.json()["created"] == 0
        assert not Message.objects.exists()

    def test_second_message_reuses_open_conversation(self, whatsapp_account):
        self._post(_sample_payload(message_id="wamid.FIRST", text="First message"))
        self._post(_sample_payload(message_id="wamid.SECOND", text="Second message"))

        assert Conversation.objects.filter(tenant=whatsapp_account.tenant).count() == 1
        assert Message.objects.filter(tenant=whatsapp_account.tenant).count() == 2


@pytest.mark.django_db
class TestWhatsAppAccountAPI:
    def test_owner_can_connect_account_token_never_returned(self, api_client, tenant_a):
        from apps.businesses.models import Business

        tenant, _, owner_a = tenant_a
        business = Business.objects.get(tenant=tenant)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/whatsapp/accounts/",
            {
                "business": str(business.id),
                "phone_number": "+254711000000",
                "phone_number_id": "999888",
                "business_account_id": "WABA_X",
                "access_token": "super-secret-token-value",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert "access_token" not in resp.data
        assert resp.data["is_connected"] is True

        account = WhatsAppAccount.objects.get(phone_number_id="999888")
        assert account.access_token == "super-secret-token-value"
        # Check the actual rendered HTTP response body, not resp.data (which
        # holds pre-render Python values like UUID that json.dumps chokes on).
        assert b"super-secret-token-value" not in resp.content

    def test_owner_cannot_read_other_tenants_account(self, api_client, tenant_b, whatsapp_account):
        """whatsapp_account belongs to tenant_a; verify tenant_b's owner can't see it."""
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_b.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/whatsapp/accounts/{whatsapp_account.id}/")
        assert resp.status_code == 404

    def test_cannot_connect_account_for_another_tenants_business(
        self, api_client, tenant_a, tenant_b
    ):
        from apps.businesses.models import Business

        _, _, owner_a = tenant_a
        tenant_b_obj, _, _ = tenant_b
        other_business = Business.objects.get(tenant=tenant_b_obj)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/whatsapp/accounts/",
            {
                "business": str(other_business.id),
                "phone_number": "+254711000000",
                "phone_number_id": "999777",
                "business_account_id": "WABA_Y",
                "access_token": "token",
            },
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestOutboundSendTask:
    def test_send_success_marks_message_sent(self, whatsapp_account, customer_a, tenant_a):
        tenant, _, owner_a = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        message = Message.objects.create(
            tenant=tenant,
            conversation=conversation,
            sender_type=Message.SenderType.STAFF,
            sender_user=owner_a,
            direction=Message.Direction.OUTBOUND,
            content="Hi!",
            status=Message.Status.PENDING,
        )

        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messages": [{"id": "wamid.OUT1"}]}

            from apps.whatsapp.tasks import send_whatsapp_message_task

            send_whatsapp_message_task(str(message.id))

        message.refresh_from_db()
        assert message.status == Message.Status.SENT
        assert message.external_message_id == "wamid.OUT1"

    def test_send_failure_marks_message_failed(self, whatsapp_account, customer_a, tenant_a):
        tenant, _, owner_a = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        message = Message.objects.create(
            tenant=tenant,
            conversation=conversation,
            sender_type=Message.SenderType.STAFF,
            sender_user=owner_a,
            direction=Message.Direction.OUTBOUND,
            content="Hi!",
            status=Message.Status.PENDING,
        )

        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 401
            mock_post.return_value.json.return_value = {"error": {"message": "Invalid token"}}

            from apps.whatsapp.tasks import send_whatsapp_message_task

            send_whatsapp_message_task(str(message.id))

        message.refresh_from_db()
        assert message.status == Message.Status.FAILED

    def test_no_connected_account_leaves_message_pending(self, customer_a, tenant_a):
        """No WhatsAppAccount exists for this tenant at all."""
        tenant, _, owner_a = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        message = Message.objects.create(
            tenant=tenant,
            conversation=conversation,
            sender_type=Message.SenderType.STAFF,
            sender_user=owner_a,
            direction=Message.Direction.OUTBOUND,
            content="Hi!",
            status=Message.Status.PENDING,
        )

        from apps.whatsapp.tasks import send_whatsapp_message_task

        send_whatsapp_message_task(str(message.id))

        message.refresh_from_db()
        assert message.status == Message.Status.PENDING
