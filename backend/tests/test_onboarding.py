"""Super-admin onboarding: create Tenant + Business + Owner atomically."""

import pytest

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.tenants.models import Tenant

from .conftest import auth_client


@pytest.mark.django_db
class TestOnboarding:
    def test_super_admin_can_onboard_a_business(self, api_client, super_admin, plan):
        client = auth_client(api_client, super_admin.email, "SuperSecret1!")
        payload = {
            "tenant_name": "New Biz Ltd",
            "business_name": "New Biz",
            "owner_email": "owner@newbiz.test",
            "owner_first_name": "Nia",
        }
        resp = client.post("/api/v1/tenants/onboard/", payload, format="json")
        assert resp.status_code == 201
        assert "temporary_password" in resp.data

        assert Tenant.objects.filter(name="New Biz Ltd").exists()
        assert Business.objects.filter(name="New Biz").exists()
        owner = User.objects.get(email="owner@newbiz.test")
        assert owner.role == User.Role.BUSINESS_OWNER
        assert owner.tenant.name == "New Biz Ltd"

    def test_non_super_admin_cannot_onboard_a_business(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        resp = client.post(
            "/api/v1/tenants/onboard/",
            {
                "tenant_name": "X",
                "business_name": "Y",
                "owner_email": "z@test.local",
                "owner_first_name": "Z",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_onboarding_rejects_duplicate_owner_email(self, api_client, super_admin, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, super_admin.email, "SuperSecret1!")
        resp = client.post(
            "/api/v1/tenants/onboard/",
            {
                "tenant_name": "Dup Co",
                "business_name": "Dup Biz",
                "owner_email": owner_a.email,
                "owner_first_name": "Dup",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_super_admin_can_suspend_and_activate_tenant(self, api_client, super_admin, tenant_a):
        tenant_a_obj, _, _ = tenant_a
        client = auth_client(api_client, super_admin.email, "SuperSecret1!")

        resp = client.post(f"/api/v1/tenants/{tenant_a_obj.id}/suspend/")
        assert resp.status_code == 200
        tenant_a_obj.refresh_from_db()
        assert tenant_a_obj.status == Tenant.Status.SUSPENDED

        resp = client.post(f"/api/v1/tenants/{tenant_a_obj.id}/activate/")
        assert resp.status_code == 200
        tenant_a_obj.refresh_from_db()
        assert tenant_a_obj.status == Tenant.Status.ACTIVE
