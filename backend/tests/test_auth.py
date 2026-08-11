"""Authentication: login, JWT claims, lockout, me, forgot/reset password."""

import pytest
from django.core import mail

from apps.accounts.models import PasswordResetToken, User

from .conftest import auth_client


@pytest.mark.django_db
class TestLogin:
    def test_login_success_prompts_mfa_setup_for_a_fresh_user(self, api_client, tenant_a):
        """
        MFA is required for every role (docs/mfa.md) — login never returns
        real tokens directly. A fresh user (no TOTP enrolled yet) gets a
        setup_token; see tests/test_mfa.py for the full enrollment/verify
        flow and `auth_client()` (tests/conftest.py) for how every other
        test transparently completes it to get a real access token.
        """
        _, _, owner_a = tenant_a
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["mfa_setup_required"] is True
        assert "setup_token" in resp.data
        assert "access" not in resp.data and "refresh" not in resp.data

    def test_login_success_for_enrolled_user_prompts_mfa_challenge(self, api_client, tenant_a):
        from .conftest import enroll_mfa

        _, _, owner_a = tenant_a
        enroll_mfa(owner_a)

        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["mfa_required"] is True
        assert "challenge_token" in resp.data
        assert "access" not in resp.data

    def test_login_wrong_password_fails(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "wrong"},
            format="json",
        )
        assert resp.status_code == 401

    def test_five_failed_logins_locks_account(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        for _ in range(5):
            api_client.post(
                "/api/v1/auth/login/",
                {"email": owner_a.email, "password": "wrong"},
                format="json",
            )
        owner_a.refresh_from_db()
        assert owner_a.is_locked

        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        assert resp.status_code == 400

    def test_me_requires_authentication(self, api_client):
        resp = api_client.get("/api/v1/auth/me/")
        assert resp.status_code == 401

    def test_me_returns_current_user(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")
        resp = client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        assert resp.data["email"] == owner_a.email


@pytest.mark.django_db
class TestPasswordReset:
    def test_forgot_password_creates_token_and_sends_email(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        resp = api_client.post(
            "/api/v1/auth/forgot-password/", {"email": owner_a.email}, format="json"
        )
        assert resp.status_code == 200
        assert PasswordResetToken.objects.filter(user=owner_a).exists()
        assert len(mail.outbox) == 1

    def test_forgot_password_unknown_email_does_not_leak(self, api_client):
        resp = api_client.post(
            "/api/v1/auth/forgot-password/",
            {"email": "nobody@nowhere.test"},
            format="json",
        )
        assert resp.status_code == 200
        assert len(mail.outbox) == 0

    def test_reset_password_with_valid_token(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        api_client.post("/api/v1/auth/forgot-password/", {"email": owner_a.email}, format="json")
        token = PasswordResetToken.objects.get(user=owner_a).token

        resp = api_client.post(
            "/api/v1/auth/reset-password/",
            {"token": token, "new_password": "BrandNewPass1!"},
            format="json",
        )
        assert resp.status_code == 200

        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "BrandNewPass1!"},
            format="json",
        )
        assert resp.status_code == 200

    def test_reset_password_with_invalid_token_fails(self, api_client):
        resp = api_client.post(
            "/api/v1/auth/reset-password/",
            {"token": "not-a-real-token", "new_password": "BrandNewPass1!"},
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
def test_super_admin_cannot_have_a_tenant():
    """DB-level CheckConstraint: super_admin_has_no_tenant."""
    from django.db import IntegrityError

    from apps.tenants.models import Tenant

    tenant = Tenant.objects.create(name="Should Not Be Allowed")
    with pytest.raises(IntegrityError):
        User.objects.create(
            email="bad-super-admin@test.local",
            role=User.Role.SUPER_ADMIN,
            tenant=tenant,
            is_superuser=True,
            first_name="Bad",
        )
