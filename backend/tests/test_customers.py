"""Customer CRM: CRUD + tenant isolation."""

import pytest

from apps.customers.models import Customer

from .conftest import auth_client


@pytest.mark.django_db
class TestCustomers:
    def test_staff_can_create_customer(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/customers/",
            {"name": "Jane Doe", "phone": "+254711111111", "source": "whatsapp"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        customer = Customer.objects.get(phone="+254711111111")
        assert customer.tenant_id == owner_a.tenant_id
        # tenant is never accepted from the client, even if sent.
        assert resp.data["tenant"] == owner_a.tenant_id

    def test_cannot_set_tenant_via_request_body(self, api_client, tenant_a, tenant_b):
        _, _, owner_a = tenant_a
        tenant_b_obj, _, _ = tenant_b
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/customers/",
            {"name": "Sneaky", "phone": "+254722222222", "tenant": str(tenant_b_obj.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["tenant"] == owner_a.tenant_id

    def test_owner_only_sees_own_tenant_customers(
        self, api_client, tenant_a, customer_a, customer_b
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/customers/")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.data["results"]]
        assert str(customer_a.id) in ids
        assert str(customer_b.id) not in ids

    def test_owner_cannot_read_other_tenants_customer(self, api_client, tenant_a, customer_b):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/customers/{customer_b.id}/")
        assert resp.status_code == 404

    def test_duplicate_phone_within_tenant_rejected(self, api_client, tenant_a, customer_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/customers/", {"name": "Dup", "phone": customer_a.phone}, format="json"
        )
        assert resp.status_code == 400

    def test_same_phone_allowed_across_different_tenants(self, tenant_a, tenant_b):
        tenant_a_obj, _, _ = tenant_a
        tenant_b_obj, _, _ = tenant_b
        Customer.objects.create(tenant=tenant_a_obj, name="X", phone="+254733333333")
        # Should not raise — the uniqueness constraint is per-tenant.
        Customer.objects.create(tenant=tenant_b_obj, name="Y", phone="+254733333333")
