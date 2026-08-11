"""
Security hardening (Phase 15): rate limiting on the four endpoints
flagged in docs/security.md as touching real external cost/impact
(the public WhatsApp webhook, /ai/test/, knowledge document uploads,
campaign sends), and the audit-logging coverage added for actions that
were previously silent (campaign sends, knowledge uploads, WhatsApp
account connection, AI settings changes, invoice generation).

Rate limits are overridden to tiny values per-test via `monkeypatch`,
directly on `SimpleRateThrottle.THROTTLE_RATES` — **not** via the
pytest-django `settings` fixture. DRF's `SimpleRateThrottle` reads its
rates from a plain class attribute (`THROTTLE_RATES = api_settings
.DEFAULT_THROTTLE_RATES`) bound once, the first time `rest_framework
.throttling` is imported (effectively at Django startup) — it is *not*
re-read per request, so reassigning `settings.REST_FRAMEWORK` later (what
the `settings` fixture does) constructs a brand new dict that the already
-bound class attribute never sees. `monkeypatch.setitem` mutates the
existing dict object in place instead (and reverts it automatically after
the test), which every throttle instance actually reads from.
"""

import hashlib
import hmac
import json

import pytest
from django.test import Client
from rest_framework.throttling import SimpleRateThrottle

from apps.ai.models import AISettings
from apps.billing.models import Invoice
from apps.common.models import AuditLog
from apps.knowledge.models import KnowledgeDocument

from .conftest import auth_client

WHATSAPP_APP_SECRET = "test-app-secret"


def _tiny_rate(monkeypatch, scope, rate="1/min"):
    monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, scope, rate)


@pytest.mark.django_db
class TestAITestThrottling:
    def test_second_request_within_the_window_is_throttled(
        self, api_client, tenant_a, monkeypatch
    ):
        tenant, business, owner_a = tenant_a
        AISettings.objects.create(tenant=tenant, business=business)
        _tiny_rate(monkeypatch, "ai_test")
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        first = client.post("/api/v1/ai/test/", {"message": "Hi"}, format="json")
        second = client.post("/api/v1/ai/test/", {"message": "Hi again"}, format="json")

        assert first.status_code == 200
        assert second.status_code == 429


@pytest.mark.django_db
class TestKnowledgeUploadThrottling:
    def test_second_upload_within_the_window_is_throttled(self, api_client, tenant_a, monkeypatch):
        _, business, owner_a = tenant_a
        _tiny_rate(monkeypatch, "knowledge_upload")
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        payload = {
            "business": str(business.id),
            "title": "Doc",
            "source_type": "text",
            "raw_text": "x",
        }

        first = client.post("/api/v1/knowledge/documents/", payload, format="json")
        second = client.post(
            "/api/v1/knowledge/documents/",
            {**payload, "title": "Doc 2"},
            format="json",
        )

        assert first.status_code == 201
        assert second.status_code == 429

    def test_listing_documents_is_not_throttled_by_the_upload_rate(
        self, api_client, tenant_a, monkeypatch
    ):
        """GET (browsing) must not share the tight upload-rate budget — see apps.knowledge.views."""
        _, _, owner_a = tenant_a
        _tiny_rate(monkeypatch, "knowledge_upload")
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        for _ in range(3):
            resp = client.get("/api/v1/knowledge/documents/")
            assert resp.status_code == 200


@pytest.mark.django_db
class TestCampaignSendThrottling:
    def test_second_send_within_the_window_is_throttled(self, api_client, tenant_a, monkeypatch):
        from apps.campaigns.models import Campaign, MessageTemplate, Segment

        tenant, business, owner_a = tenant_a
        template = MessageTemplate.objects.create(
            tenant=tenant,
            business=business,
            name="T",
            body_text="Hi",
            status=MessageTemplate.Status.APPROVED,
            whatsapp_template_name="t",
        )
        segment = Segment.objects.create(tenant=tenant, business=business, name="S")
        campaign_1 = Campaign.objects.create(
            tenant=tenant,
            business=business,
            segment=segment,
            template=template,
            name="C1",
        )
        campaign_2 = Campaign.objects.create(
            tenant=tenant,
            business=business,
            segment=segment,
            template=template,
            name="C2",
        )
        _tiny_rate(monkeypatch, "campaign_send")
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        first = client.post(f"/api/v1/campaigns/{campaign_1.id}/send/")
        second = client.post(f"/api/v1/campaigns/{campaign_2.id}/send/")

        assert first.status_code == 200
        assert second.status_code == 429


@pytest.mark.django_db
class TestWhatsAppWebhookThrottling:
    @pytest.fixture(autouse=True)
    def _webhook_settings(self, settings):
        settings.WHATSAPP_APP_SECRET = WHATSAPP_APP_SECRET

    def _sign(self, body: bytes) -> str:
        digest = hmac.new(WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_third_request_within_the_window_is_throttled(self, monkeypatch):
        _tiny_rate(monkeypatch, "whatsapp_webhook", rate="2/min")
        client = Client()
        body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()

        responses = [
            client.generic(
                "POST",
                "/api/v1/whatsapp/webhook/",
                data=body,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256=self._sign(body),
            )
            for _ in range(3)
        ]

        assert [r.status_code for r in responses] == [200, 200, 429]


@pytest.mark.django_db
class TestAuditLoggingCoverage:
    """
    Every action added to apps.billing/campaigns/knowledge/whatsapp/ai
    this phase now writes an AuditLog row — this class proves each one
    actually fires, not just that the underlying action succeeds.
    """

    def test_whatsapp_account_connection_logged(self, api_client, tenant_a, settings):
        settings.WHATSAPP_TOKEN_ENCRYPTION_KEY = "u_aeZR2Zfksak3SwNr-u-kzLvYRTIhDnd2HMd1dFqZM="
        _, business, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/whatsapp/accounts/",
            {
                "business": str(business.id),
                "phone_number": "+254700000000",
                "phone_number_id": "1",
                "business_account_id": "W1",
                "access_token": "tok",
            },
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert AuditLog.objects.filter(action="WHATSAPP_ACCOUNT_CONNECTED").exists()

    def test_knowledge_upload_logged(self, api_client, tenant_a):
        _, business, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/knowledge/documents/",
            {"business": str(business.id), "title": "D", "source_type": "text", "raw_text": "x"},
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert AuditLog.objects.filter(action="KNOWLEDGE_DOCUMENT_UPLOADED").exists()
        assert KnowledgeDocument.objects.count() == 1

    def test_ai_settings_update_logged(self, api_client, tenant_a):
        tenant, business, owner_a = tenant_a
        AISettings.objects.create(tenant=tenant, business=business)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch("/api/v1/ai/settings/", {"assistant_name": "Nia"}, format="json")

        assert resp.status_code == 200, resp.data
        log = AuditLog.objects.get(action="AI_SETTINGS_UPDATED")
        assert "assistant_name" in log.metadata["changed_fields"]

    def test_invoice_generation_logged(self, api_client, super_admin, tenant_a):
        tenant, _, _ = tenant_a
        api_client.force_authenticate(user=super_admin)

        resp = api_client.post(
            "/api/v1/billing/invoices/generate/", {"tenant": str(tenant.id)}, format="json"
        )

        assert resp.status_code == 201, resp.data
        assert AuditLog.objects.filter(action="INVOICE_GENERATED").exists()
        assert Invoice.objects.count() == 1

    def test_campaign_send_logged(self, api_client, tenant_a):
        from apps.campaigns.models import Campaign, MessageTemplate, Segment

        tenant, business, owner_a = tenant_a
        template = MessageTemplate.objects.create(
            tenant=tenant,
            business=business,
            name="T",
            body_text="Hi",
            status=MessageTemplate.Status.APPROVED,
            whatsapp_template_name="t",
        )
        segment = Segment.objects.create(tenant=tenant, business=business, name="S")
        campaign = Campaign.objects.create(
            tenant=tenant,
            business=business,
            segment=segment,
            template=template,
            name="C",
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/send/")

        assert resp.status_code == 200, resp.data
        assert AuditLog.objects.filter(action="CAMPAIGN_SENT").exists()
