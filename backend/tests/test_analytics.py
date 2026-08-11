"""
Analytics: per-tenant dashboard metrics (funnel, conversation/message
counts, currency-grouped revenue, AI performance, response time, top
questions) computed live from real data, platform-wide stats for super
admins, and the API surface (tenant isolation, RBAC, date-range bounds).
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.analytics import platform_services, services
from apps.common.models import AuditLog
from apps.conversations.models import Conversation
from apps.customers.models import Customer
from apps.messages.models import Message
from apps.orders.models import Order, OrderItem
from apps.products.models import Product

from .conftest import auth_client


def _message(tenant, conversation, *, sender_type, direction, content="hi", minutes_offset=0):
    message = Message.objects.create(
        tenant=tenant,
        conversation=conversation,
        sender_type=sender_type,
        direction=direction,
        content=content,
        status=Message.Status.DELIVERED,
    )
    if minutes_offset:
        message.created_at = timezone.now() + timezone.timedelta(minutes=minutes_offset)
        message.save(update_fields=["created_at"])
    return message


@pytest.mark.django_db
class TestCustomerFunnel:
    def test_counts_each_status(self, tenant_a):
        tenant, _, _ = tenant_a
        Customer.objects.create(
            tenant=tenant, name="A", phone="+254700900001", status=Customer.Status.NEW
        )
        Customer.objects.create(
            tenant=tenant, name="B", phone="+254700900002", status=Customer.Status.QUALIFIED
        )
        Customer.objects.create(
            tenant=tenant, name="C", phone="+254700900003", status=Customer.Status.QUALIFIED
        )

        result = services.customer_funnel(tenant)

        assert result["new"] == 1
        assert result["qualified"] == 2
        assert result["converted"] == 0


@pytest.mark.django_db
class TestConversationCounts:
    def test_counts_by_status_and_total(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        Conversation.objects.create(
            tenant=tenant, customer=customer_a, status=Conversation.Status.OPEN
        )
        Conversation.objects.create(
            tenant=tenant, customer=customer_a, status=Conversation.Status.CLOSED
        )

        result = services.conversation_counts(tenant)

        assert result["open"] == 1
        assert result["closed"] == 1
        assert result["total"] == 2


@pytest.mark.django_db
class TestOrderRevenue:
    def test_groups_revenue_by_currency_and_excludes_pending_cancelled(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        product = Product.objects.create(tenant=tenant, name="P", price=Decimal("100.00"), stock=5)

        confirmed = Order.objects.create(
            tenant=tenant, customer=customer_a, status=Order.Status.CONFIRMED, currency="KES"
        )
        OrderItem.objects.create(
            tenant=tenant,
            order=confirmed,
            product=product,
            product_name="P",
            unit_price=Decimal("100.00"),
            quantity=2,
        )
        confirmed.recalculate_total()

        pending = Order.objects.create(
            tenant=tenant,
            customer=customer_a,
            status=Order.Status.PENDING,
            currency="KES",
            total_amount=Decimal("999.00"),
        )
        cancelled = Order.objects.create(
            tenant=tenant,
            customer=customer_a,
            status=Order.Status.CANCELLED,
            currency="KES",
            total_amount=Decimal("999.00"),
        )
        other_currency = Order.objects.create(
            tenant=tenant,
            customer=customer_a,
            status=Order.Status.DELIVERED,
            currency="USD",
            total_amount=Decimal("50.00"),
        )

        result = services.order_revenue(tenant)

        assert result["revenue_by_currency"]["KES"] == Decimal("200.00")
        assert result["revenue_by_currency"]["USD"] == Decimal("50.00")
        assert result["by_status"]["pending"] == 1
        assert result["by_status"]["cancelled"] == 1
        assert (
            pending.id and cancelled.id and other_currency.id
        )  # created, just not counted as revenue


@pytest.mark.django_db
class TestAIPerformance:
    def test_counts_ai_replies_and_handoffs(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.AI,
            direction=Message.Direction.OUTBOUND,
        )
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.AI,
            direction=Message.Direction.OUTBOUND,
        )
        AuditLog.log(action="AI_HANDOFF", tenant=tenant, metadata={"reason": "test"})

        result = services.ai_performance(tenant)

        assert result["ai_replies_sent"] == 2
        assert result["handoffs"] == 1


@pytest.mark.django_db
class TestAverageResponseTime:
    def test_no_messages_returns_none(self, tenant_a):
        tenant, _, _ = tenant_a
        result = services.average_response_time(tenant)
        assert result == {"average_seconds": None, "sample_count": 0}

    def test_single_inbound_outbound_pair(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            minutes_offset=0,
        )
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.STAFF,
            direction=Message.Direction.OUTBOUND,
            minutes_offset=5,
        )

        result = services.average_response_time(tenant)

        assert result["sample_count"] == 1
        assert (
            290 <= result["average_seconds"] <= 310
        )  # ~5 minutes, allowing for test execution time

    def test_consecutive_inbound_messages_count_as_one_wait(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            minutes_offset=0,
        )
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            minutes_offset=1,
        )
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.STAFF,
            direction=Message.Direction.OUTBOUND,
            minutes_offset=10,
        )

        result = services.average_response_time(tenant)

        # Measured from the FIRST unanswered inbound (t=0), not the second (t=1).
        assert result["sample_count"] == 1
        assert 595 <= result["average_seconds"] <= 605


@pytest.mark.django_db
class TestTopCustomerQuestions:
    def test_only_repeated_questions_included(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        for _ in range(3):
            _message(
                tenant,
                conversation,
                sender_type=Message.SenderType.CUSTOMER,
                direction=Message.Direction.INBOUND,
                content="Do you deliver to Arusha?",
            )
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            content="A one-off question nobody else asked",
        )

        result = services.top_customer_questions(tenant)

        assert len(result) == 1
        assert result[0]["text"] == "Do you deliver to Arusha?"
        assert result[0]["count"] == 3

    def test_normalizes_whitespace_and_case_for_grouping(self, tenant_a, customer_a):
        tenant, _, _ = tenant_a
        conversation = Conversation.objects.create(tenant=tenant, customer=customer_a)
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            content="What time do you open?",
        )
        _message(
            tenant,
            conversation,
            sender_type=Message.SenderType.CUSTOMER,
            direction=Message.Direction.INBOUND,
            content="  what time DO you open?  ",
        )

        result = services.top_customer_questions(tenant)

        assert len(result) == 1
        assert result[0]["count"] == 2


@pytest.mark.django_db
class TestPlatformServices:
    def test_tenant_counts(self, tenant_a, tenant_b):
        result = platform_services.tenant_counts()
        assert result["active"] == 2
        assert result["total"] == 2

    def test_user_counts_includes_super_admin(self, super_admin, tenant_a):
        result = platform_services.user_counts()
        assert result["super_admin"] == 1
        assert result["business_owner"] == 1

    def test_platform_dashboard_shape(self, tenant_a):
        result = platform_services.platform_dashboard()
        assert set(result) == {
            "tenants",
            "businesses",
            "users",
            "conversations",
            "messages",
            "orders",
            "signup_trend",
        }


@pytest.mark.django_db
class TestAnalyticsDashboardAPI:
    def test_staff_can_view_own_tenant_dashboard(self, api_client, tenant_a, customer_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/analytics/dashboard/")

        assert resp.status_code == 200, resp.data
        assert "funnel" in resp.data
        assert "top_questions" in resp.data

    def test_tenant_isolation(self, api_client, tenant_a, tenant_b, customer_a):
        tenant, _, owner_a = tenant_a
        Customer.objects.create(tenant=tenant, name="X", phone="+254700900099")

        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_b.email, "OwnerSecret1!")

        resp = client.get("/api/v1/analytics/dashboard/")

        assert resp.status_code == 200
        assert resp.data["funnel"]["new"] == 0  # tenant_b has no customers of its own here

    def test_invalid_date_bound_rejected(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/analytics/dashboard/?start=not-a-date")

        assert resp.status_code == 400

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get("/api/v1/analytics/dashboard/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestPlatformAnalyticsAPI:
    def test_super_admin_can_view(self, api_client, super_admin, tenant_a):
        api_client.force_authenticate(user=super_admin)

        resp = api_client.get("/api/v1/analytics/platform/")

        assert resp.status_code == 200, resp.data
        assert resp.data["tenants"]["total"] == 1

    def test_business_owner_cannot_view(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/analytics/platform/")

        assert resp.status_code == 403
