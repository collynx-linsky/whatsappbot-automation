from decimal import Decimal

import pyotp
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.businesses.models import Business
from apps.customers.models import Customer
from apps.products.models import Product
from apps.tenants.models import Plan, Tenant


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """
    DRF's throttle classes (enabled platform-wide — see
    config/settings/base.py's REST_FRAMEWORK) store request counters in
    Django's cache, and CACHES uses LocMemCache in tests
    (config/settings/test.py) — which persists for the whole pytest
    process, not per-test. Without this, request counts would accumulate
    across the entire suite (hundreds of anonymous/authenticated requests
    across 200+ tests) and eventually trip a real rate limit inside an
    unrelated test. Clearing before every test keeps throttling itself
    genuinely testable (tests/test_security.py overrides a rate to
    something tiny and asserts a real 429) without it silently
    contaminating everything else.
    """
    cache.clear()


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


@pytest.fixture
def product_a(tenant_a):
    # Decimal, not a plain string — Django's DecimalField does NOT coerce an
    # assigned value until it round-trips through the DB (full_clean() or a
    # save+refetch); a raw string left in memory makes `unit_price * quantity`
    # do Python string repetition ("100.00" * 2 == "100.00100.00"), not
    # arithmetic. Bit us once in tests/test_orders.py — see git history.
    tenant, _, _ = tenant_a
    return Product.objects.create(
        tenant=tenant, name="Product A", price=Decimal("100.00"), stock=10
    )


@pytest.fixture
def product_b(tenant_b):
    tenant, _, _ = tenant_b
    return Product.objects.create(
        tenant=tenant, name="Product B", price=Decimal("200.00"), stock=5
    )


def auth_client(api_client, email, password):
    """
    Logs in AND completes MFA — required for every role, no exceptions
    (see docs/mfa.md) — so the client this returns carries a real, fully
    -authenticated access token, exactly like a real client would end up
    with. `POST /api/v1/auth/login/` never returns one directly anymore;
    it returns either a `setup_token` (first login — this helper enrolls
    TOTP with a fresh secret, computes a valid code via `pyotp`, and
    confirms) or a `challenge_token` (already enrolled — computes a valid
    code against the user's real stored secret and verifies). Either path
    ends with a real access token, same as production.
    """
    resp = api_client.post(
        "/api/v1/auth/login/", {"email": email, "password": password}, format="json"
    )
    assert resp.status_code == 200, resp.data

    if resp.data.get("mfa_setup_required"):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['setup_token']}")
        setup_resp = api_client.post("/api/v1/auth/mfa/setup/")
        assert setup_resp.status_code == 200, setup_resp.data
        code = pyotp.TOTP(setup_resp.data["secret"]).now()
        confirm_resp = api_client.post(
            "/api/v1/auth/mfa/setup/confirm/", {"code": code}, format="json"
        )
        assert confirm_resp.status_code == 200, confirm_resp.data
        token = confirm_resp.data["access"]
    else:
        assert resp.data.get("mfa_required"), resp.data
        user = User.objects.get(email__iexact=email)
        code = pyotp.TOTP(user.mfa_secret).now()
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['challenge_token']}")
        verify_resp = api_client.post("/api/v1/auth/mfa/verify/", {"code": code}, format="json")
        assert verify_resp.status_code == 200, verify_resp.data
        token = verify_resp.data["access"]

    api_client.token = token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


def enroll_mfa(user) -> str:
    """
    Test-only shortcut: enrolls `user` in MFA directly (bypassing the
    setup/confirm API round trip) with a fresh secret, returning it so
    the caller can compute valid codes. For tests that specifically
    exercise the *already-enrolled* login path or MFA-specific edge cases
    (wrong code, backup codes, lockout) without needing the enrollment
    flow itself to be part of the test.
    """
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = True
    user.save(update_fields=["mfa_secret_encrypted", "mfa_enabled"])
    return secret
