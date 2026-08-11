"""
MFA (TOTP), required for every role — docs/mfa.md. Covers the full
enrollment flow, the challenge flow for an already-enrolled user, backup
codes, the token-purpose isolation (a setup_token can't be used for
verify or any normal endpoint, a real access token can't be used for
either MFA endpoint), and the reset flow (Business Owner / Super Admin).
"""

import pyotp
import pytest

from apps.accounts.models import MFABackupCode, User

from .conftest import auth_client, enroll_mfa


@pytest.mark.django_db
class TestMFASetupFlow:
    def test_setup_returns_secret_and_provisioning_uri(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['setup_token']}")

        resp = api_client.post("/api/v1/auth/mfa/setup/")

        assert resp.status_code == 200, resp.data
        assert len(resp.data["secret"]) >= 16
        assert resp.data["provisioning_uri"].startswith("otpauth://totp/")

    def test_confirm_with_valid_code_enables_mfa_and_issues_tokens(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['setup_token']}")
        setup = api_client.post("/api/v1/auth/mfa/setup/")
        code = pyotp.TOTP(setup.data["secret"]).now()

        resp = api_client.post("/api/v1/auth/mfa/setup/confirm/", {"code": code}, format="json")

        assert resp.status_code == 200, resp.data
        assert "access" in resp.data and "refresh" in resp.data
        assert len(resp.data["backup_codes"]) == 10
        owner_a.refresh_from_db()
        assert owner_a.mfa_enabled is True
        assert MFABackupCode.objects.filter(user=owner_a).count() == 10

    def test_confirm_with_wrong_code_rejected(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['setup_token']}")
        api_client.post("/api/v1/auth/mfa/setup/")

        resp = api_client.post(
            "/api/v1/auth/mfa/setup/confirm/", {"code": "000000"}, format="json"
        )

        assert resp.status_code == 400
        owner_a.refresh_from_db()
        assert owner_a.mfa_enabled is False

    def test_confirm_without_calling_setup_first_rejected(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['setup_token']}")

        resp = api_client.post(
            "/api/v1/auth/mfa/setup/confirm/", {"code": "123456"}, format="json"
        )

        assert resp.status_code == 400


@pytest.mark.django_db
class TestMFAChallengeFlow:
    def test_verify_with_valid_totp_code_issues_tokens(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        secret = enroll_mfa(owner_a)
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['challenge_token']}")

        resp = api_client.post(
            "/api/v1/auth/mfa/verify/", {"code": pyotp.TOTP(secret).now()}, format="json"
        )

        assert resp.status_code == 200, resp.data
        assert "access" in resp.data and "refresh" in resp.data

    def test_verify_with_wrong_code_rejected_and_counts_toward_lockout(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        enroll_mfa(owner_a)
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['challenge_token']}")

        resp = api_client.post("/api/v1/auth/mfa/verify/", {"code": "000000"}, format="json")

        assert resp.status_code == 400
        owner_a.refresh_from_db()
        assert owner_a.failed_login_attempts == 1

    def test_verify_with_backup_code_issues_tokens_and_consumes_it(self, api_client, tenant_a):
        from apps.accounts import mfa as mfa_service

        _, _, owner_a = tenant_a
        enroll_mfa(owner_a)
        codes = mfa_service.generate_backup_codes()
        mfa_service.store_backup_codes(owner_a, codes)

        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['challenge_token']}")

        resp = api_client.post(
            "/api/v1/auth/mfa/verify/", {"backup_code": codes[0]}, format="json"
        )
        assert resp.status_code == 200, resp.data

        # Second login attempt with the SAME (now-used) code must fail.
        login_2 = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_2.data['challenge_token']}")
        reuse_resp = api_client.post(
            "/api/v1/auth/mfa/verify/", {"backup_code": codes[0]}, format="json"
        )
        assert reuse_resp.status_code == 400

    def test_neither_code_nor_backup_code_rejected(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        enroll_mfa(owner_a)
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['challenge_token']}")

        resp = api_client.post("/api/v1/auth/mfa/verify/", {}, format="json")

        assert resp.status_code == 400


@pytest.mark.django_db
class TestMFATokenPurposeIsolation:
    def test_setup_token_cannot_call_verify(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['setup_token']}")

        resp = api_client.post("/api/v1/auth/mfa/verify/", {"code": "123456"}, format="json")

        assert resp.status_code == 403

    def test_challenge_token_cannot_call_setup(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        enroll_mfa(owner_a)
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['challenge_token']}")

        resp = api_client.post("/api/v1/auth/mfa/setup/")

        assert resp.status_code == 403

    def test_real_access_token_cannot_call_mfa_endpoints(self, api_client, tenant_a):
        _, _, owner_a = tenant_a
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post("/api/v1/auth/mfa/verify/", {"code": "123456"}, format="json")

        assert resp.status_code == 403

    def test_purpose_tagged_token_cannot_call_a_normal_endpoint(self, api_client, tenant_a):
        """core.authentication.FullAccessJWTAuthentication — refused platform-wide,
        not just by the MFA endpoints' own permission checks."""
        _, _, owner_a = tenant_a
        login = api_client.post(
            "/api/v1/auth/login/",
            {"email": owner_a.email, "password": "OwnerSecret1!"},
            format="json",
        )
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['setup_token']}")

        resp = api_client.get("/api/v1/customers/")

        assert resp.status_code == 401


@pytest.mark.django_db
class TestMFAReset:
    def test_business_owner_can_reset_staff_mfa(self, api_client, tenant_a):
        tenant, _, owner_a = tenant_a
        staff = User.objects.create_user(
            email="staff-mfa@test.local",
            password="StaffSecret1!",
            first_name="Staff",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        enroll_mfa(staff)
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        resp = client.post(f"/api/v1/staff/{staff.id}/mfa-reset/")

        assert resp.status_code == 200, resp.data
        staff.refresh_from_db()
        assert staff.mfa_enabled is False
        assert staff.mfa_secret_encrypted == ""
        assert not MFABackupCode.objects.filter(user=staff).exists()

    def test_business_owner_cannot_reset_another_owner_via_this_endpoint(
        self, api_client, tenant_a, tenant_b
    ):
        _, _, owner_a = tenant_a
        _, _, owner_b = tenant_b
        client = auth_client(api_client, owner_a.email, "OwnerSecret1!")

        # owner_b isn't even in owner_a's tenant, so this 404s before the role check —
        # proving tenant isolation holds here too, not just the role restriction.
        resp = client.post(f"/api/v1/staff/{owner_b.id}/mfa-reset/")

        assert resp.status_code == 404

    def test_super_admin_can_reset_any_users_mfa(self, api_client, super_admin, tenant_a):
        _, _, owner_a = tenant_a
        enroll_mfa(owner_a)
        api_client.force_authenticate(user=super_admin)

        resp = api_client.post(f"/api/v1/staff/{owner_a.id}/mfa-reset/")

        assert resp.status_code == 200, resp.data
        owner_a.refresh_from_db()
        assert owner_a.mfa_enabled is False

    def test_staff_cannot_reset_anyones_mfa(self, api_client, tenant_a):
        tenant, _, _ = tenant_a
        staff = User.objects.create_user(
            email="staff-reset@test.local",
            password="StaffSecret1!",
            first_name="Staff",
            role=User.Role.STAFF,
            tenant=tenant,
        )
        client = auth_client(api_client, staff.email, "StaffSecret1!")

        resp = client.post(f"/api/v1/staff/{staff.id}/mfa-reset/")

        assert resp.status_code == 403
