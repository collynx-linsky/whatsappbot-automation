"""Products: CRUD, permissions, tenant isolation."""

from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.common.models import AuditLog
from apps.products.models import Product

from .conftest import auth_client


@pytest.mark.django_db
class TestProducts:
    def test_manager_can_create_product(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/products/",
            {"name": "Samsung 55in TV", "price": "850000.00", "currency": "TZS", "stock": 5},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["is_orderable"] is True
        assert AuditLog.objects.filter(action="PRODUCT_CREATED", user=owner_a).exists()

    def test_staff_can_list_but_not_create(self, api_client, tenant_a):
        tenant, _, _ = tenant_a
        staff = User.objects.create_user(
            email="staff-products@test.local",
            password="StaffSecret1!",
            first_name="Staff",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, staff.email, "StaffSecret1!")

        resp = client.get("/api/v1/products/")
        assert resp.status_code == 200

        resp = client.post("/api/v1/products/", {"name": "X", "price": "1.00"}, format="json")
        assert resp.status_code == 403

    def test_owner_cannot_see_other_tenants_products(
        self, api_client, tenant_a, product_a, product_b
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/products/")
        ids = [p["id"] for p in resp.data["results"]]
        assert str(product_a.id) in ids
        assert str(product_b.id) not in ids

    def test_owner_cannot_read_other_tenants_product_directly(
        self, api_client, tenant_a, product_b
    ):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/products/{product_b.id}/")
        assert resp.status_code == 404

    def test_update_logs_audit(self, api_client, tenant_a, product_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(f"/api/v1/products/{product_a.id}/", {"stock": 0}, format="json")
        assert resp.status_code == 200
        assert resp.data["is_orderable"] is False
        assert AuditLog.objects.filter(action="PRODUCT_UPDATED", user=owner_a).exists()

    def test_duplicate_sku_within_tenant_rejected_at_db_level(self, tenant_a):
        tenant, _, _ = tenant_a
        Product.objects.create(tenant=tenant, name="A", sku="SKU1", price=Decimal("1.00"))
        # A second product with the same SKU in the same tenant should be
        # blocked by the partial unique constraint (empty-string SKUs excluded).
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Product.objects.create(tenant=tenant, name="B", sku="SKU1", price=Decimal("2.00"))
