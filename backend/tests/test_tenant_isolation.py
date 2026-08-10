"""
Critical test (spec section 29): Business A cannot access Business B's data.
"""

import pytest

from .conftest import auth_client


@pytest.mark.django_db
class TestTenantIsolation:
    def test_owner_sees_only_own_business_in_list(self, api_client, tenant_a, tenant_b):
        _, business_a, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/businesses/")
        assert resp.status_code == 200
        ids = [b["id"] for b in resp.data["results"]]
        assert str(business_a.id) in ids
        assert len(ids) == 1

    def test_owner_cannot_read_other_tenants_business_by_id(self, api_client, tenant_a, tenant_b):
        _, _, owner_a = tenant_a
        _, business_b, _ = tenant_b
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get(f"/api/v1/businesses/{business_b.id}/")
        # 404, not 403 — existence of another tenant's object is not leaked.
        assert resp.status_code == 404

    def test_owner_cannot_write_other_tenants_business(self, api_client, tenant_a, tenant_b):
        _, _, owner_a = tenant_a
        _, business_b, _ = tenant_b
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            f"/api/v1/businesses/{business_b.id}/", {"name": "HACKED"}, format="json"
        )
        assert resp.status_code == 404

        business_b.refresh_from_db()
        assert business_b.name == "Business B"

    def test_owner_can_write_own_business(self, api_client, tenant_a):
        _, business_a, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            f"/api/v1/businesses/{business_a.id}/", {"city": "Nairobi"}, format="json"
        )
        assert resp.status_code == 200
        business_a.refresh_from_db()
        assert business_a.city == "Nairobi"

    def test_x_tenant_id_header_cannot_be_used_to_impersonate_another_tenant(
        self, api_client, tenant_a, tenant_b
    ):
        """
        A regular (non-superuser) user must not be able to reach another
        tenant's data by spoofing X-Tenant-ID — the header is only honored
        for super admins (core.middleware.TenantMiddleware).
        """
        _, _, owner_a = tenant_a
        tenant_b_obj, business_b, _ = tenant_b
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {client.token}",
            HTTP_X_TENANT_ID=str(tenant_b_obj.id),
        )

        resp = client.get(f"/api/v1/businesses/{business_b.id}/")
        assert resp.status_code == 404

    def test_super_admin_can_see_all_businesses(self, api_client, super_admin, tenant_a, tenant_b):
        _, business_a, _ = tenant_a
        _, business_b, _ = tenant_b
        client = auth_client(api_client, super_admin.email, "SuperSecret1!")

        resp = client.get("/api/v1/businesses/")
        assert resp.status_code == 200
        ids = {b["id"] for b in resp.data["results"]}
        assert str(business_a.id) in ids
        assert str(business_b.id) in ids

    def test_non_super_admin_cannot_list_all_tenants(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/tenants/")
        assert resp.status_code == 403
