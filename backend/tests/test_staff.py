"""Staff management: create/list/update, tenant isolation, owner-only, self/owner-lockout protection."""

import pytest
from django.core import mail

from apps.accounts.models import User
from apps.common.models import AuditLog

from .conftest import auth_client


@pytest.mark.django_db
class TestStaffList:
    def test_owner_sees_own_tenant_roster_including_self(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/staff/")
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.data["results"]]
        assert owner_a.email in emails

    def test_owner_does_not_see_other_tenants_roster(self, api_client, tenant_a, tenant_b):
        _, _, owner_a = tenant_a
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.get("/api/v1/staff/")
        emails = [u["email"] for u in resp.data["results"]]
        assert owner_b.email not in emails


@pytest.mark.django_db
class TestStaffCreate:
    def test_owner_can_add_staff(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {
                "email": "new-staff@test.local",
                "first_name": "New",
                "last_name": "Staffer",
                "role": "staff",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert "temporary_password" in resp.data
        assert resp.data["user"]["role"] == "staff"

        new_user = User.objects.get(email="new-staff@test.local")
        assert new_user.tenant_id == tenant.id
        assert new_user.check_password(resp.data["temporary_password"])
        assert len(mail.outbox) == 1
        assert AuditLog.objects.filter(action="STAFF_ADDED", tenant=tenant).exists()

    def test_owner_can_add_manager(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": "new-manager@test.local", "first_name": "New", "role": "manager"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["user"]["role"] == "manager"

    def test_cannot_create_another_business_owner(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": "wannabe-owner@test.local", "first_name": "X", "role": "business_owner"},
            format="json",
        )
        assert resp.status_code == 400

    def test_cannot_create_super_admin(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": "wannabe-admin@test.local", "first_name": "X", "role": "super_admin"},
            format="json",
        )
        assert resp.status_code == 400

    def test_staff_role_cannot_add_staff(self, api_client, tenant_a):
        """Only BUSINESS_OWNER (or super admin) can add staff — not Manager or Staff themselves."""
        tenant, _, owner_a = tenant_a
        staff_user = User.objects.create_user(
            email="existing-staff@test.local",
            password="StaffSecret1!",
            first_name="Existing",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, staff_user.email, "StaffSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": "another@test.local", "first_name": "X", "role": "staff"},
            format="json",
        )
        assert resp.status_code == 403

    def test_duplicate_email_rejected(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": owner_a.email, "first_name": "Dup", "role": "staff"},
            format="json",
        )
        assert resp.status_code == 400

    def test_super_admin_cannot_add_staff_without_a_tenant(self, api_client, super_admin):
        client = auth_client(api_client, super_admin.email, "SuperSecret1!")

        resp = client.post(
            "/api/v1/staff/",
            {"email": "orphan@test.local", "first_name": "X", "role": "staff"},
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestStaffUpdate:
    def test_owner_can_promote_staff_to_manager(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        staff_user = User.objects.create_user(
            email="promote-me@test.local",
            password="StaffSecret1!",
            first_name="Promote",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(f"/api/v1/staff/{staff_user.id}/", {"role": "manager"}, format="json")
        assert resp.status_code == 200
        staff_user.refresh_from_db()
        assert staff_user.role == User.Role.MANAGER

    def test_owner_can_deactivate_staff(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        staff_user = User.objects.create_user(
            email="deactivate-me@test.local",
            password="StaffSecret1!",
            first_name="Deactivate",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(f"/api/v1/staff/{staff_user.id}/", {"is_active": False}, format="json")
        assert resp.status_code == 200
        staff_user.refresh_from_db()
        assert staff_user.is_active is False

    def test_owner_cannot_modify_own_account_via_staff_endpoint(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(f"/api/v1/staff/{owner_a.id}/", {"is_active": False}, format="json")
        assert resp.status_code == 400
        owner_a.refresh_from_db()
        assert owner_a.is_active is True

    def test_cannot_escalate_staff_to_business_owner(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        staff_user = User.objects.create_user(
            email="escalate-me@test.local",
            password="StaffSecret1!",
            first_name="Escalate",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            f"/api/v1/staff/{staff_user.id}/", {"role": "business_owner"}, format="json"
        )
        assert resp.status_code == 400
        staff_user.refresh_from_db()
        assert staff_user.role == User.Role.STAFF

    def test_owner_cannot_modify_staff_in_another_tenant(self, api_client, tenant_a, tenant_b):
        tenant_b_obj, _, owner_b = tenant_b
        other_staff = User.objects.create_user(
            email="other-tenant-staff@test.local",
            password="StaffSecret1!",
            first_name="Other",
            role=User.Role.STAFF,
            tenant=tenant_b_obj,
        )
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.patch(
            f"/api/v1/staff/{other_staff.id}/", {"is_active": False}, format="json"
        )
        assert resp.status_code == 404

    def test_manager_cannot_patch_staff(self, api_client, tenant_a):
        """Only BUSINESS_OWNER can PATCH — Manager can view but not edit the roster."""
        tenant, _, owner_a = tenant_a
        manager = User.objects.create_user(
            email="manager@test.local",
            password="ManagerSecret1!",
            first_name="Manager",
            role=User.Role.MANAGER,
            tenant=tenant,
        )
        staff_user = User.objects.create_user(
            email="target-staff@test.local",
            password="StaffSecret1!",
            first_name="Target",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, manager.email, "ManagerSecret1!")

        resp = client.patch(f"/api/v1/staff/{staff_user.id}/", {"is_active": False}, format="json")
        assert resp.status_code == 403
