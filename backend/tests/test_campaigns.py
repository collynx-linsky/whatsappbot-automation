"""
Marketing campaigns: segment filtering (opt-in enforced structurally),
template variable counting, the full send pipeline (mocked WhatsApp HTTP
for success/failure, real for the "no template approved"/"no WhatsApp
account"/"no opted-in recipients" structural-failure paths, which are
genuinely reachable without any credentials), and the API surface.
"""

from unittest.mock import patch

import pytest

from apps.campaigns.models import Campaign, CampaignRecipient, MessageTemplate, Segment
from apps.campaigns.services import (
    get_segment_customers,
    prepare_campaign_recipients,
    send_campaign,
)
from apps.customers.models import Customer
from apps.messages.models import Message
from apps.whatsapp.models import WhatsAppAccount

from .conftest import auth_client

WHATSAPP_TOKEN_KEY = "u_aeZR2Zfksak3SwNr-u-kzLvYRTIhDnd2HMd1dFqZM="


@pytest.fixture(autouse=True)
def _whatsapp_settings(settings):
    settings.WHATSAPP_TOKEN_ENCRYPTION_KEY = WHATSAPP_TOKEN_KEY


@pytest.fixture
def opted_in_customer(tenant_a):
    tenant, _, _ = tenant_a
    return Customer.objects.create(
        tenant=tenant,
        name="Opted In",
        phone="+254700555001",
        status=Customer.Status.QUALIFIED,
        marketing_opt_in=True,
    )


@pytest.fixture
def opted_out_customer(tenant_a):
    tenant, _, _ = tenant_a
    return Customer.objects.create(
        tenant=tenant,
        name="Opted Out",
        phone="+254700555002",
        status=Customer.Status.QUALIFIED,
        marketing_opt_in=False,
    )


@pytest.fixture
def segment_a(tenant_a):
    tenant, business, owner = tenant_a
    return Segment.objects.create(
        tenant=tenant,
        business=business,
        created_by=owner,
        name="Qualified leads",
        filters={"statuses": ["qualified"]},
    )


@pytest.fixture
def approved_template(tenant_a):
    tenant, business, owner = tenant_a
    return MessageTemplate.objects.create(
        tenant=tenant,
        business=business,
        created_by=owner,
        name="Promo",
        whatsapp_template_name="promo_v1",
        body_text="Hi {{1}}, enjoy {{2}}% off this week!",
        status=MessageTemplate.Status.APPROVED,
    )


@pytest.fixture
def campaign_a(tenant_a, segment_a, approved_template):
    tenant, business, owner = tenant_a
    return Campaign.objects.create(
        tenant=tenant,
        business=business,
        segment=segment_a,
        template=approved_template,
        created_by=owner,
        name="Spring Sale",
        template_variables=["Amina", "20"],
    )


@pytest.fixture
def connected_account(tenant_a):
    tenant, business, _ = tenant_a
    account = WhatsAppAccount(
        tenant=tenant,
        business=business,
        phone_number="+254700000000",
        phone_number_id="123456",
        business_account_id="WABA_ID",
    )
    account.access_token = "real-token"
    account.save()
    account.mark_connected()
    return account


class TestMessageTemplate:
    def test_variable_count_counts_distinct_placeholders(self):
        template = MessageTemplate(body_text="Hi {{1}}, your order {{2}} is ready. Thanks {{1}}!")
        assert template.variable_count == 2

    def test_variable_count_zero_for_static_text(self):
        template = MessageTemplate(body_text="Thanks for shopping with us!")
        assert template.variable_count == 0


@pytest.mark.django_db
class TestGetSegmentCustomers:
    def test_excludes_non_opted_in_customers(
        self, tenant_a, segment_a, opted_in_customer, opted_out_customer
    ):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()
        opted_out_customer.status = Customer.Status.QUALIFIED
        opted_out_customer.save()

        results = get_segment_customers(segment_a)

        assert list(results) == [opted_in_customer]

    def test_filters_by_status(self, tenant_a, segment_a, opted_in_customer):
        tenant, _, _ = tenant_a
        other = Customer.objects.create(
            tenant=tenant,
            name="New lead",
            phone="+254700555003",
            status=Customer.Status.NEW,
            marketing_opt_in=True,
        )
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()

        results = get_segment_customers(segment_a)

        assert opted_in_customer in results
        assert other not in results

    def test_filters_by_tags_any_match(self, tenant_a):
        tenant, business, owner = tenant_a
        segment = Segment.objects.create(
            tenant=tenant,
            business=business,
            created_by=owner,
            name="VIPs",
            filters={"tags": ["vip"]},
        )
        vip = Customer.objects.create(
            tenant=tenant,
            name="VIP",
            phone="+254700555004",
            marketing_opt_in=True,
            tags=["vip", "returning"],
        )
        regular = Customer.objects.create(
            tenant=tenant,
            name="Regular",
            phone="+254700555005",
            marketing_opt_in=True,
            tags=["new"],
        )

        results = get_segment_customers(segment)

        assert vip in results
        assert regular not in results

    def test_empty_filters_matches_all_opted_in(self, tenant_a):
        tenant, business, owner = tenant_a
        segment = Segment.objects.create(
            tenant=tenant,
            business=business,
            created_by=owner,
            name="Everyone",
            filters={},
        )
        Customer.objects.create(
            tenant=tenant,
            name="A",
            phone="+254700555006",
            marketing_opt_in=True,
        )
        Customer.objects.create(
            tenant=tenant,
            name="B",
            phone="+254700555007",
            marketing_opt_in=False,
        )

        results = get_segment_customers(segment)

        assert results.count() == 1


@pytest.mark.django_db
class TestPrepareCampaignRecipients:
    def test_snapshots_segment_customers(self, campaign_a, opted_in_customer):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()

        count = prepare_campaign_recipients(campaign_a)

        assert count == 1
        assert CampaignRecipient.objects.filter(
            campaign=campaign_a, customer=opted_in_customer
        ).exists()

    def test_idempotent_on_repeated_calls(self, campaign_a, opted_in_customer):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()

        prepare_campaign_recipients(campaign_a)
        prepare_campaign_recipients(campaign_a)

        assert CampaignRecipient.objects.filter(campaign=campaign_a).count() == 1


@pytest.mark.django_db
class TestSendCampaign:
    def test_fails_without_approved_template(self, campaign_a, connected_account):
        campaign_a.template.status = MessageTemplate.Status.PENDING_APPROVAL
        campaign_a.template.save()

        send_campaign(campaign_a)
        campaign_a.refresh_from_db()

        assert campaign_a.status == Campaign.Status.FAILED
        assert "approved" in campaign_a.error_message.lower()

    def test_fails_without_connected_whatsapp_account(self, campaign_a):
        send_campaign(campaign_a)
        campaign_a.refresh_from_db()

        assert campaign_a.status == Campaign.Status.FAILED
        assert "whatsapp account" in campaign_a.error_message.lower()

    def test_fails_with_no_opted_in_recipients(self, campaign_a, connected_account):
        send_campaign(campaign_a)
        campaign_a.refresh_from_db()

        assert campaign_a.status == Campaign.Status.FAILED
        assert "opted-in" in campaign_a.error_message.lower()

    def test_successful_send_creates_message_and_updates_counts(
        self, campaign_a, connected_account, opted_in_customer
    ):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()

        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messages": [{"id": "wamid.CAMPAIGN1"}]}
            send_campaign(campaign_a)

        campaign_a.refresh_from_db()
        assert campaign_a.status == Campaign.Status.SENT
        assert campaign_a.sent_count == 1
        assert campaign_a.failed_count == 0
        assert campaign_a.recipient_count == 1

        message = Message.objects.get(
            tenant=campaign_a.tenant, sender_type=Message.SenderType.CAMPAIGN
        )
        assert message.status == Message.Status.SENT
        assert message.external_message_id == "wamid.CAMPAIGN1"
        assert "Amina" in message.content and "20" in message.content

        recipient = CampaignRecipient.objects.get(campaign=campaign_a, customer=opted_in_customer)
        assert recipient.status == CampaignRecipient.Status.SENT
        assert recipient.message == message

        # Verify the actual outbound HTTP payload used the template endpoint, not free text.
        sent_payload = mock_post.call_args.kwargs["json"]
        assert sent_payload["type"] == "template"
        assert sent_payload["template"]["name"] == "promo_v1"

    def test_provider_failure_marks_recipient_failed_not_whole_campaign(
        self, campaign_a, connected_account, opted_in_customer
    ):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()

        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 401
            mock_post.return_value.json.return_value = {"error": {"message": "Invalid token"}}
            send_campaign(campaign_a)

        campaign_a.refresh_from_db()
        assert campaign_a.status == Campaign.Status.SENT  # attempted, not a structural failure
        assert campaign_a.failed_count == 1
        assert campaign_a.sent_count == 0

        recipient = CampaignRecipient.objects.get(campaign=campaign_a, customer=opted_in_customer)
        assert recipient.status == CampaignRecipient.Status.FAILED
        assert recipient.error_message

    def test_opted_out_between_scheduling_and_send_is_skipped(
        self, campaign_a, connected_account, opted_in_customer
    ):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()
        prepare_campaign_recipients(campaign_a)
        # Customer opts out after being snapshotted onto the campaign.
        opted_in_customer.marketing_opt_in = False
        opted_in_customer.save()

        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            send_campaign(campaign_a)

        mock_post.assert_not_called()
        campaign_a.refresh_from_db()
        assert campaign_a.skipped_count == 1
        recipient = CampaignRecipient.objects.get(campaign=campaign_a, customer=opted_in_customer)
        assert recipient.status == CampaignRecipient.Status.SKIPPED
        assert recipient.skip_reason == "not opted in"


@pytest.mark.django_db
class TestMessageTemplateAPI:
    def test_manager_can_create_template(self, api_client, tenant_a):
        _, business, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/campaigns/templates/",
            {
                "business": str(business.id),
                "name": "Welcome",
                "body_text": "Hi {{1}}!",
                "category": "marketing",
            },
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert resp.data["status"] == "draft"
        assert resp.data["variable_count"] == 1

    def test_staff_cannot_create_template(self, api_client, tenant_a):
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
            "/api/v1/campaigns/templates/",
            {"business": str(business.id), "name": "X", "body_text": "Hi"},
            format="json",
        )

        assert resp.status_code == 403

    def test_manager_can_approve_template(self, api_client, tenant_a):
        tenant, business, owner_a = tenant_a
        template = MessageTemplate.objects.create(
            tenant=tenant,
            business=business,
            name="Promo",
            body_text="Hi",
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            f"/api/v1/campaigns/templates/{template.id}/",
            {"status": "approved", "whatsapp_template_name": "promo_v1"},
            format="json",
        )

        assert resp.status_code == 200, resp.data
        template.refresh_from_db()
        assert template.status == MessageTemplate.Status.APPROVED

    def test_tenant_isolation(self, api_client, tenant_a, tenant_b):
        tenant, business, _ = tenant_a
        template = MessageTemplate.objects.create(
            tenant=tenant, business=business, name="X", body_text="Hi"
        )
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_b.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/campaigns/templates/{template.id}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestSegmentAPI:
    def test_manager_can_create_segment(self, api_client, tenant_a):
        _, business, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/campaigns/segments/",
            {"business": str(business.id), "name": "Leads", "filters": {"statuses": ["new"]}},
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert resp.data["customer_count"] == 0

    def test_rejects_unknown_filter_keys(self, api_client, tenant_a):
        _, business, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/campaigns/segments/",
            {"business": str(business.id), "name": "Bad", "filters": {"nonsense": ["x"]}},
            format="json",
        )

        assert resp.status_code == 400

    def test_preview_returns_matching_customers(
        self, api_client, tenant_a, segment_a, opted_in_customer
    ):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/campaigns/segments/{segment_a.id}/preview/")

        assert resp.status_code == 200, resp.data
        assert resp.data["customer_count"] == 1
        assert resp.data["sample"][0]["phone"] == opted_in_customer.phone


@pytest.mark.django_db
class TestCampaignAPI:
    def test_manager_can_create_campaign(self, api_client, tenant_a, segment_a, approved_template):
        _, business, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/campaigns/",
            {
                "business": str(business.id),
                "segment": str(segment_a.id),
                "template": str(approved_template.id),
                "name": "Launch",
                "template_variables": ["Amina", "20"],
            },
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert resp.data["status"] == "draft"

    def test_rejects_segment_from_another_business(
        self, api_client, tenant_a, tenant_b, approved_template
    ):
        _, business, owner_a = tenant_a
        other_tenant, other_business, other_owner = tenant_b
        other_segment = Segment.objects.create(
            tenant=other_tenant,
            business=other_business,
            created_by=other_owner,
            name="Other",
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/campaigns/",
            {
                "business": str(business.id),
                "segment": str(other_segment.id),
                "template": str(approved_template.id),
                "name": "Bad",
            },
            format="json",
        )

        assert resp.status_code == 400

    def test_send_view_queues_and_transitions_to_scheduled(self, api_client, tenant_a, campaign_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messages": [{"id": "wamid.X"}]}
            resp = client.post(f"/api/v1/campaigns/{campaign_a.id}/send/")

        assert resp.status_code == 200, resp.data
        # Celery is eager in tests, so by the time this returns the real send already
        # ran and the campaign moved past "scheduled" to a terminal state.
        campaign_a.refresh_from_db()
        assert campaign_a.status in (Campaign.Status.SENT, Campaign.Status.FAILED)

    def test_cannot_resend_an_already_sent_campaign(self, api_client, tenant_a, campaign_a):
        campaign_a.status = Campaign.Status.SENT
        campaign_a.save()
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(f"/api/v1/campaigns/{campaign_a.id}/send/")

        assert resp.status_code == 400

    def test_staff_cannot_send_campaign(self, api_client, tenant_a, campaign_a):
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

        resp = client.post(f"/api/v1/campaigns/{campaign_a.id}/send/")

        assert resp.status_code == 403

    def test_recipients_endpoint_lists_outcomes(
        self, api_client, tenant_a, campaign_a, connected_account, opted_in_customer
    ):
        opted_in_customer.status = Customer.Status.QUALIFIED
        opted_in_customer.save()
        with patch("apps.whatsapp.providers.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messages": [{"id": "wamid.X"}]}
            send_campaign(campaign_a)

        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        resp = client.get(f"/api/v1/campaigns/{campaign_a.id}/recipients/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["status"] == "sent"


@pytest.mark.django_db
class TestCustomerOptIn:
    def test_opting_in_stamps_timestamp(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        customer = Customer.objects.create(tenant=tenant, name="C", phone="+254700555099")
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            f"/api/v1/customers/{customer.id}/", {"marketing_opt_in": True}, format="json"
        )

        assert resp.status_code == 200, resp.data
        assert resp.data["marketing_opt_in"] is True
        assert resp.data["marketing_opt_in_at"] is not None

    def test_defaults_to_not_opted_in(self, tenant_a):
        tenant, _, _ = tenant_a
        customer = Customer.objects.create(tenant=tenant, name="C", phone="+254700555098")
        assert customer.marketing_opt_in is False
        assert customer.marketing_opt_in_at is None
