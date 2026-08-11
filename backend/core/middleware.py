"""
WhatsAppBusinessAI — Core Middleware

- TenantMiddleware: resolves `request.tenant`.
- RequestLoggingMiddleware: structured request logging.
- SecurityHeadersMiddleware: CSP + Permissions-Policy (headers Django has
  no built-in setting for — see docs/security.md).
"""

import logging
import time
import uuid

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("waba")


class TenantMiddleware(MiddlewareMixin):
    """
    Resolves `request.tenant` from server-side authenticated state only.

    Rule (per platform security policy — tenant_id is never trusted from the
    client): for an ordinary authenticated user, `request.tenant` is always
    their own `user.tenant`, full stop — no header, query param, or body
    field can override it. A super admin has no tenant of their own, so for
    super-admin-only endpoints that need to act on a specific tenant (e.g.
    "view Business X as super admin"), the `X-Tenant-ID` header is honored
    *only* when the authenticated user `is_superuser`, and only after
    verifying the tenant exists. Regular users cannot use this header to
    reach another tenant's data — permission classes in core.permissions
    additionally enforce `request.user.tenant_id == request.tenant.id` for
    tenant-scoped views, so this middleware is a convenience, not the sole
    authorization boundary.

    Note: this runs as plain Django middleware, which executes *before* DRF
    resolves `request.user` for JWT-authenticated requests (DRF's
    authentication classes only run once the view starts processing the
    DRF-wrapped Request). So this middleware authenticates the JWT itself
    (the same class DRF uses) to know who the caller is early enough to
    attach `request.tenant` — it does not trust an unverified claim.
    """

    def process_request(self, request):
        request.tenant = None
        user = self._authenticate(request)
        if user is None:
            return

        if not user.is_superuser and getattr(user, "tenant_id", None):
            request.tenant = user.tenant
            return

        if user.is_superuser:
            tenant_id = request.META.get("HTTP_X_TENANT_ID")
            if tenant_id:
                from apps.tenants.models import Tenant

                request.tenant = Tenant.objects.filter(id=tenant_id).first()

    @staticmethod
    def _authenticate(request):
        # FullAccessJWTAuthentication, not plain JWTAuthentication — a
        # token minted for the MFA setup/challenge flow (apps.accounts.mfa)
        # must never resolve request.tenant either, even though DRF's own
        # authentication layer (which runs later, at view dispatch) would
        # independently reject such a token before any view logic ran.
        # Belt-and-suspenders: this middleware should never even
        # transiently treat a not-yet-fully-authenticated request as
        # "this is tenant X."
        from rest_framework.exceptions import AuthenticationFailed
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

        from core.authentication import FullAccessJWTAuthentication

        try:
            result = FullAccessJWTAuthentication().authenticate(request)
        except (InvalidToken, TokenError, AuthenticationFailed):
            # AuthenticationFailed specifically covers a purpose-tagged
            # MFA token here — FullAccessJWTAuthentication.get_user()
            # raises it deliberately (see core/authentication.py), and
            # this middleware treats that exactly like "no authenticated
            # user," not a request-ending error — DRF's own view-level
            # authentication is what actually turns it into a real 401
            # response for the caller.
            return None
        if result is None:
            return None
        user, _token = result
        return user

    def process_response(self, request, response):
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Logs all API requests with method, path, status code, and duration."""

    def process_request(self, request):
        request._start_time = time.time()
        request._request_id = str(uuid.uuid4())

    def process_response(self, request, response):
        if not hasattr(request, "_start_time"):
            return response

        duration_ms = round((time.time() - request._start_time) * 1000, 2)
        tenant = getattr(request, "tenant", None)

        log_data = {
            "request_id": getattr(request, "_request_id", ""),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "tenant_id": str(tenant.id) if tenant else None,
            "ip": self._get_client_ip(request),
        }

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            level,
            "HTTP %s %s -> %s (%sms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            extra=log_data,
        )

        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds Content-Security-Policy and Permissions-Policy — the two
    meaningful security headers Django's own `SecurityMiddleware` has no
    setting for (HSTS/nosniff/referrer-policy/frame-options are all
    already covered by Django settings — see config/settings/production.py).

    This is a JSON API first (DEFAULT_RENDERER_CLASSES is JSONRenderer
    only — the browsable API is never served), so CSP mostly matters for
    the two real HTML surfaces this backend does serve: the Django admin
    and drf-spectacular's Swagger/Redoc docs pages
    (`/api/docs/`, `/api/redoc/`), which load their UI assets from
    `cdn.jsdelivr.net` by default (drf-spectacular's own
    `SWAGGER_UI_DIST`/`REDOC_DIST` settings) — explicitly allowlisted
    below rather than switching to `drf-spectacular-sidecar` (a new
    dependency) to serve those assets locally instead.
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://cdn.jsdelivr.net; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=(), payment=()"

    def process_response(self, request, response):
        # DEBUG-only relaxation isn't needed — the CSP above already
        # allows everything this app's own dev tooling (Django admin,
        # drf-spectacular docs) needs, in every environment.
        response.setdefault("Content-Security-Policy", self.CSP)
        response.setdefault("Permissions-Policy", self.PERMISSIONS_POLICY)
        return response
