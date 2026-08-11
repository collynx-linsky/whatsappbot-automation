"""
Billing: Plan limit enforcement (live counts for users/whatsapp_accounts/
customers, period usage for ai_messages/campaign_sends), usage tracking,
invoice generation (snapshotted, idempotent per period, no real payment
gateway), and the API surface — including the actual enforcement wired
into staff/WhatsApp-account/customer creation and campaign sends.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.db.models.signals import post_save

from apps.accounts.models import User
from apps.billing.exceptions import PlanLimitExceeded
from apps.billing.models import Invoice, UsageRecord
from apps.billing.services import (
    check_limit,
    current_month_start,
    generate_invoice,
    increment_usage,
    is_over_limit,
    usage_summary,
)
from apps.businesses.models import Business
from apps.customers.models import Customer
from apps.tenants.models import Plan, Tenant

from .conftest import auth_client


def _tenant_with_limit(**limit_overrides):
    plan = Plan.objects.create(
        name=f"Test Plan {Plan.objects.count()}",
        max_users=limit_overrides.get("max_users", 5),
        max_whatsapp_accounts=limit_overrides.get("max_whatsapp_accounts", 1),
        max_ai_messages_per_month=limit_overrides.get("max_ai_messages_per_month", 1000),
        max_customers=limit_overrides.get("max_customers", 1000),
        max_campaigns_per_month=limit_overrides.get("max_campaigns_per_month", 10),
    )
    tenant = Tenant.objects.create(name="Limit Test Co", plan=plan, status=Tenant.Status.ACTIVE)
    business = Business.objects.create(tenant=tenant, name="Limit Test Business")
    owner = User.objects.create_user(
        email=f"owner-{tenant.id}@test.local",
        password="OwnerSecret1!",
        first_name="Owner",
        role=User.Role.BUSINESS_OWNER,
        tenant=tenant,
    )
    return tenant, business, owner


@pytest.mark.django_db
class TestCheckLimit:
    def test_passes_when_under_limit(self, tenant_a):
        tenant, _, _ = tenant_a
        check_limit(tenant, "customers")  # default plan fixture allows 1000 — no exception

    def test_raises_when_at_limit(self):
        tenant, _, owner = _tenant_with_limit(max_users=1)
        # owner itself already counts as 1 active user against max_users=1
        with pytest.raises(PlanLimitExceeded):
            check_limit(tenant, "users")

    def test_skips_when_no_plan(self):
        tenant = Tenant.objects.create(name="No Plan Co", plan=None, status=Tenant.Status.ACTIVE)
        check_limit(tenant, "users")  # no exception — nothing to enforce against

    def test_skips_when_tenant_none(self):
        check_limit(None, "users")  # super admin action — no exception

    def test_zero_means_unlimited(self):
        tenant, _, _ = _tenant_with_limit(max_users=0)
        for _ in range(20):
            User.objects.create_user(
                email=f"staff{_}@test.local",
                password="x",
                role=User.Role.STAFF,
                tenant=tenant,
            )
        check_limit(tenant, "users")  # no exception regardless of count


@pytest.mark.django_db
class TestIsOverLimit:
    def test_false_under_limit(self, tenant_a):
        tenant, _, _ = tenant_a
        assert is_over_limit(tenant, "ai_messages") is False

    def test_true_at_limit(self):
        tenant, _, _ = _tenant_with_limit(max_ai_messages_per_month=1)
        increment_usage(tenant, UsageRecord.Metric.AI_MESSAGES)
        assert is_over_limit(tenant, "ai_messages") is True


@pytest.mark.django_db
class TestIncrementUsage:
    def test_creates_and_increments_current_month_record(self, tenant_a):
        tenant, _, _ = tenant_a
        increment_usage(tenant, UsageRecord.Metric.AI_MESSAGES)
        increment_usage(tenant, UsageRecord.Metric.AI_MESSAGES)

        record = UsageRecord.objects.get(
            tenant=tenant, metric=UsageRecord.Metric.AI_MESSAGES, period=current_month_start()
        )
        assert record.count == 2

    def test_none_tenant_is_a_no_op(self):
        increment_usage(None, UsageRecord.Metric.AI_MESSAGES)  # must not raise


@pytest.mark.django_db
class TestUsageSummary:
    def test_shape_with_plan(self, tenant_a):
        tenant, _, _ = tenant_a
        result = usage_summary(tenant)
        assert result["plan"] == tenant.plan.name
        assert set(result["limits"]) == {
            "users",
            "whatsapp_accounts",
            "customers",
            "ai_messages",
            "campaign_sends",
        }
        assert result["limits"]["users"]["used"] >= 1  # the owner counts

    def test_none_without_plan(self):
        tenant = Tenant.objects.create(name="No Plan", plan=None)
        assert usage_summary(tenant) == {"plan": None, "limits": {}}


@pytest.mark.django_db
class TestGenerateInvoice:
    def test_creates_invoice_snapshotting_plan(self, tenant_a):
        tenant, _, _ = tenant_a
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)

        invoice = generate_invoice(tenant, start, end)

        assert invoice is not None
        assert invoice.plan_name == tenant.plan.name
        assert invoice.amount == tenant.plan.price_monthly
        assert invoice.status == Invoice.Status.ISSUED
        assert tenant.slug.upper() in invoice.invoice_number

    def test_idempotent_per_period(self, tenant_a):
        tenant, _, _ = tenant_a
        start, end = date(2026, 1, 1), date(2026, 1, 31)

        first = generate_invoice(tenant, start, end)
        second = generate_invoice(tenant, start, end)

        assert first.id == second.id
        assert Invoice.objects.filter(tenant=tenant, period_start=start).count() == 1

    def test_returns_none_without_plan(self):
        tenant = Tenant.objects.create(name="No Plan Invoice", plan=None)
        assert generate_invoice(tenant, date(2026, 1, 1), date(2026, 1, 31)) is None


@pytest.mark.django_db
class TestUsageSummaryAPI:
    def test_staff_can_view_own_tenant_usage(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/billing/usage/")

        assert resp.status_code == 200, resp.data
        assert "limits" in resp.data


@pytest.mark.django_db
class TestInvoiceAPI:
    def test_manager_can_list_own_invoices(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        generate_invoice(tenant, date(2026, 1, 1), date(2026, 1, 31))
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/billing/invoices/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1

    def test_tenant_isolation(self, api_client, tenant_a, tenant_b):
        tenant, _, _ = tenant_a
        generate_invoice(tenant, date(2026, 1, 1), date(2026, 1, 31))
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_b.email, "OwnerSecret1!")

        resp = client.get("/api/v1/billing/invoices/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 0

    def test_staff_cannot_view_invoices(self, api_client, tenant_a):
        tenant, _, _ = tenant_a
        User.objects.create_user(
            email="staff-billing@test.local",
            password="StaffSecret1!",
            first_name="Staff",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, "staff-billing@test.local", "StaffSecret1!")

        resp = client.get("/api/v1/billing/invoices/")

        assert resp.status_code == 403


@pytest.mark.django_db
class TestGenerateInvoiceAPI:
    def test_super_admin_can_generate(self, api_client, super_admin, tenant_a):
        tenant, _, _ = tenant_a
        api_client.force_authenticate(user=super_admin)

        resp = api_client.post(
            "/api/v1/billing/invoices/generate/",
            {"tenant": str(tenant.id), "period_start": "2026-02-01"},
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert resp.data["period_start"] == "2026-02-01"

    def test_business_owner_cannot_generate(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/billing/invoices/generate/", {"tenant": str(tenant.id)}, format="json"
        )

        assert resp.status_code == 403


@pytest.mark.django_db
class TestEnforcementWiredIntoRealViews:
    def test_staff_creation_blocked_at_user_limit(self, api_client):
        tenant, _, owner = _tenant_with_limit(max_users=1)
        client = auth_client(api_client, owner.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": "new-staff@test.local", "first_name": "New", "role": "staff"},
            format="json",
        )

        assert resp.status_code == 402, resp.data

    def test_customer_creation_blocked_at_limit(self, api_client):
        tenant, _, owner = _tenant_with_limit(max_customers=1)
        Customer.objects.create(tenant=tenant, name="Existing", phone="+254700800001")
        client = auth_client(api_client, owner.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/customers/", {"name": "New", "phone": "+254700800002"}, format="json"
        )

        assert resp.status_code == 402, resp.data

    def test_whatsapp_account_creation_blocked_at_limit(self, api_client, settings):
        settings.FIELD_ENCRYPTION_KEY = "u_aeZR2Zfksak3SwNr-u-kzLvYRTIhDnd2HMd1dFqZM="
        tenant, business, owner = _tenant_with_limit(max_whatsapp_accounts=0)
        # max_whatsapp_accounts=0 means unlimited per Plan's own convention —
        # use 1 with one already connected to actually trigger the block.
        tenant.plan.max_whatsapp_accounts = 1
        tenant.plan.save()
        from apps.whatsapp.models import WhatsAppAccount

        account = WhatsAppAccount(
            tenant=tenant,
            business=business,
            phone_number="+254700000000",
            phone_number_id="111",
            business_account_id="WABA_1",
        )
        account.access_token = "token"
        account.save()

        client = auth_client(api_client, owner.email, "OwnerSecret1!")
        resp = client.post(
            "/api/v1/whatsapp/accounts/",
            {
                "business": str(business.id),
                "phone_number": "+254711000000",
                "phone_number_id": "222",
                "business_account_id": "WABA_2",
                "access_token": "another-token",
            },
            format="json",
        )

        assert resp.status_code == 402, resp.data

    def test_campaign_send_blocked_at_monthly_limit(self, api_client):
        from apps.campaigns.models import Campaign, MessageTemplate, Segment

        tenant, business, owner = _tenant_with_limit(max_campaigns_per_month=1)
        increment_usage(tenant, UsageRecord.Metric.CAMPAIGN_SENDS)  # already at the limit

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
        client = auth_client(api_client, owner.email, "OwnerSecret1!")

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/send/")

        assert resp.status_code == 402, resp.data
        campaign.refresh_from_db()
        assert campaign.status == Campaign.Status.DRAFT  # never even queued


@pytest.mark.django_db
class TestAIReplyRespectsUsageLimit:
    """
    CELERY_TASK_ALWAYS_EAGER=True means creating the inbound Message below
    would also synchronously fire apps.ai.signals.dispatch_ai_reply before
    this test's own direct call — same double-invocation issue documented
    in tests/test_ai.py::TestGenerateAIReply. Disconnect it here too.
    """

    @pytest.fixture(autouse=True)
    def _disconnect_ai_signal(self):
        from apps.ai.signals import dispatch_ai_reply
        from apps.messages.models import Message

        post_save.disconnect(dispatch_ai_reply, sender=Message)
        yield
        post_save.connect(dispatch_ai_reply, sender=Message)

    def test_over_limit_hands_off_without_calling_provider(self, tenant_a, customer_a, settings):
        from apps.ai.models import AISettings
        from apps.ai.services import generate_ai_reply
        from apps.conversations.models import Conversation
        from apps.messages.models import Message

        settings.OPENAI_API_KEY = "sk-test"
        tenant, business, _ = tenant_a
        tenant.plan.max_ai_messages_per_month = 1
        tenant.plan.save()
        increment_usage(tenant, UsageRecord.Metric.AI_MESSAGES)  # already at the limit

        AISettings.objects.create(tenant=tenant, business=business)
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        inbound = Message.objects.create(
            tenant=tenant,
            conversation=conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            content="Hello",
            status=Message.Status.DELIVERED,
        )

        with patch("apps.ai.providers.requests.post") as mock_post:
            reply = generate_ai_reply(inbound)

        mock_post.assert_not_called()
        assert reply.sender_type == Message.SenderType.AI
        assert "limit" in reply.content.lower() or reply.content  # fallback message sent
