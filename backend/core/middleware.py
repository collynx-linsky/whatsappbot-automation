"""
WhatsAppBusinessAI — Core Middleware

- TenantMiddleware: resolves `request.tenant`.
- RequestLoggingMiddleware: structured request logging.
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
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

        try:
            result = JWTAuthentication().authenticate(request)
        except (InvalidToken, TokenError):
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
