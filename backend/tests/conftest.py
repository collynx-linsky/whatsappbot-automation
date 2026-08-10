import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.customers.models import Customer
from apps.tenants.models import Plan, Tenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def plan(db):
    return Plan.objects.create(name="Starter", is_default=True)


@pytest.fixture
def super_admin(db):
    return User.objects.create_superuser(
        email="admin@wabaai.local", password="SuperSecret1!", first_name="Platform"
    )


def _make_tenant_with_owner(plan, tenant_name, business_name, owner_email):
    tenant = Tenant.objects.create(name=tenant_name, plan=plan, status=Tenant.Status.ACTIVE)
    business = Business.objects.create(tenant=tenant, name=business_name)
    owner = User.objects.create_user(
        email=owner_email,
        password="OwnerSecret1!",
        first_name="Owner",
        role=User.Role.BUSINESS_OWNER,
        tenant=tenant,
    )
    return tenant, business, owner


@pytest.fixture
def tenant_a(db, plan):
    return _make_tenant_with_owner(plan, "Tenant A Ltd", "Business A", "owner-a@test.local")


@pytest.fixture
def tenant_b(db, plan):
    return _make_tenant_with_owner(plan, "Tenant B Ltd", "Business B", "owner-b@test.local")


@pytest.fixture
def customer_a(tenant_a):
    tenant, _, _ = tenant_a
    return Customer.objects.create(tenant=tenant, name="Customer A", phone="+254700000001")


@pytest.fixture
def customer_b(tenant_b):
    tenant, _, _ = tenant_b
    return Customer.objects.create(tenant=tenant, name="Customer B", phone="+254700000002")


def auth_client(api_client, email, password):
    resp = api_client.post(
        "/api/v1/auth/login/", {"email": email, "password": password}, format="json"
    )
    assert resp.status_code == 200, resp.data
    token = resp.data["access"]
    api_client.token = token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client
