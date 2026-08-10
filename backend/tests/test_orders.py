"""Orders: nested creation, total calculation, status state machine, tenant isolation."""

import pytest

from apps.common.models import AuditLog
from apps.orders.models import Order

from .conftest import auth_client


@pytest.mark.django_db
class TestOrderCreation:
    def test_create_order_with_items_computes_total(
        self, api_client, tenant_a, customer_a, product_a
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/orders/",
            {
                "customer": str(customer_a.id),
                "items": [{"product": str(product_a.id), "quantity": 3}],
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["status"] == "pending"
        assert resp.data["total_amount"] == "300.00"  # 100.00 * 3
        assert len(resp.data["items"]) == 1
        assert resp.data["items"][0]["product_name"] == "Product A"
        assert AuditLog.objects.filter(action="ORDER_CREATED").exists()

    def test_price_snapshot_survives_later_product_price_change(
        self, api_client, tenant_a, customer_a, product_a
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/orders/",
            {
                "customer": str(customer_a.id),
                "items": [{"product": str(product_a.id), "quantity": 1}],
            },
            format="json",
        )
        order_id = resp.data["id"]

        product_a.price = "999.00"
        product_a.save(update_fields=["price"])

        resp = client.get(f"/api/v1/orders/{order_id}/")
        assert resp.data["total_amount"] == "100.00"  # unaffected by the later price change
        assert resp.data["items"][0]["unit_price"] == "100.00"

    def test_cannot_order_another_tenants_product(
        self, api_client, tenant_a, customer_a, product_b
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/orders/",
            {
                "customer": str(customer_a.id),
                "items": [{"product": str(product_b.id), "quantity": 1}],
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_cannot_order_for_another_tenants_customer(
        self, api_client, tenant_a, customer_b, product_a
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/orders/",
            {
                "customer": str(customer_b.id),
                "items": [{"product": str(product_a.id), "quantity": 1}],
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_order_requires_at_least_one_item(self, api_client, tenant_a, customer_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/orders/", {"customer": str(customer_a.id), "items": []}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestOrderStatusTransitions:
    def _create_order(self, client, customer, product, quantity=1):
        resp = client.post(
            "/api/v1/orders/",
            {
                "customer": str(customer.id),
                "items": [{"product": str(product.id), "quantity": quantity}],
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        return resp.data["id"]

    def test_pending_to_confirmed_stamps_confirmed_by(
        self, api_client, tenant_a, customer_a, product_a
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        order_id = self._create_order(client, customer_a, product_a)

        resp = client.post(
            f"/api/v1/orders/{order_id}/status/", {"status": "confirmed"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "confirmed"
        assert resp.data["confirmed_by_name"] == owner_a.get_full_name()
        assert resp.data["confirmed_at"] is not None

    def test_cannot_skip_straight_to_processing(self, api_client, tenant_a, customer_a, product_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        order_id = self._create_order(client, customer_a, product_a)

        resp = client.post(
            f"/api/v1/orders/{order_id}/status/", {"status": "processing"}, format="json"
        )
        assert resp.status_code == 400

        order = Order.objects.get(pk=order_id)
        assert order.status == Order.Status.PENDING

    def test_cannot_move_backwards(self, api_client, tenant_a, customer_a, product_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        order_id = self._create_order(client, customer_a, product_a)

        client.post(f"/api/v1/orders/{order_id}/status/", {"status": "confirmed"}, format="json")
        resp = client.post(
            f"/api/v1/orders/{order_id}/status/", {"status": "pending"}, format="json"
        )
        assert resp.status_code == 400

    def test_cannot_transition_a_terminal_order(self, api_client, tenant_a, customer_a, product_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        order_id = self._create_order(client, customer_a, product_a)

        client.post(f"/api/v1/orders/{order_id}/status/", {"status": "cancelled"}, format="json")
        resp = client.post(
            f"/api/v1/orders/{order_id}/status/", {"status": "confirmed"}, format="json"
        )
        assert resp.status_code == 400

    def test_owner_cannot_transition_other_tenants_order(
        self, api_client, tenant_a, tenant_b, customer_b, product_b
    ):
        _, _, owner_b = tenant_b
        client_b = auth_client(api_client, owner_b.email, "OwnerSecret1!")
        order_id = self._create_order(client_b, customer_b, product_b)

        api_client_a = type(api_client)()
        _, _, owner_a = tenant_a
        client_a = auth_client(api_client_a, owner_a.email, "OwnerSecret1!")

        resp = client_a.post(
            f"/api/v1/orders/{order_id}/status/", {"status": "confirmed"}, format="json"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
def test_stock_is_independent_of_order_creation(tenant_a, customer_a, product_a):
    """
    Documents current behavior: creating an order does NOT decrement
    Product.stock automatically — inventory management is manual for now
    (see docs/ROADMAP.md). Not testing an API call here, just the model
    contract, so a future change to this behavior fails a test on purpose.
    """
    initial_stock = product_a.stock
    from apps.orders.models import Order, OrderItem

    order = Order.objects.create(tenant=product_a.tenant, customer=customer_a)
    OrderItem.objects.create(
        tenant=product_a.tenant,
        order=order,
        product=product_a,
        product_name=product_a.name,
        unit_price=product_a.price,
        quantity=2,
    )
    product_a.refresh_from_db()
    assert product_a.stock == initial_stock
