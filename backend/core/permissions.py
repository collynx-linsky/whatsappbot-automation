"""
WhatsAppBusinessAI — Custom DRF Permission Classes

Enforces the platform's 4 fixed roles (SUPER_ADMIN, BUSINESS_OWNER, MANAGER,
STAFF — see apps.accounts.models.User.Role) server-side. Never trust a
tenant/business id supplied by the client; these classes always compare
against `request.user`'s own tenant/role.
"""

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsSuperAdmin(BasePermission):
    """Only platform super admins can access."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsBusinessOwner(BasePermission):
    """The BUSINESS_OWNER role within their own tenant, or a super admin (platform oversight)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.role == user.Role.BUSINESS_OWNER)
        )


class IsManagerOrAbove(BasePermission):
    """BUSINESS_OWNER or MANAGER within their own tenant, or a super admin (platform oversight)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.role in (user.Role.BUSINESS_OWNER, user.Role.MANAGER))
        )


class IsStaffOrAbove(BasePermission):
    """Any tenant-side role (BUSINESS_OWNER, MANAGER, STAFF), or a super admin (platform oversight)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or user.role in (user.Role.BUSINESS_OWNER, user.Role.MANAGER, user.Role.STAFF)
            )
        )


class IsTenantMember(IsAuthenticated):
    """
    User must belong to the tenant resolved on the request
    (`request.tenant`, set by core.middleware.TenantMiddleware from
    server-side authenticated state — never from a client-supplied id).
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        return request.user.tenant_id == tenant.id


class IsOwnerOfObject(BasePermission):
    """Object-level check: the object's `tenant_id` must match the user's own tenant."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        tenant_id = getattr(obj, "tenant_id", None)
        return tenant_id is not None and tenant_id == request.user.tenant_id


class IsMFAPending(BasePermission):
    """
    Only the three MFA setup/challenge endpoints use this (see
    apps.accounts.mfa_views) — they authenticate via the plain
    `rest_framework_simplejwt.authentication.JWTAuthentication` (not the
    platform default `core.authentication.FullAccessJWTAuthentication`,
    which refuses purpose-tagged tokens outright), and this permission
    then checks the token actually carries the *specific* purpose this
    view expects (`view.mfa_purpose`) — a "mfa_setup" token can't be used
    to call the "mfa_challenge" endpoint or vice versa, and a real,
    already-fully-authenticated access token (no `purpose` claim at all)
    is rejected here too, not just tokens for the wrong stage.
    """

    def has_permission(self, request, view):
        purpose = getattr(view, "mfa_purpose", None)
        if not purpose or not request.user or not request.user.is_authenticated:
            return False
        if not request.auth:
            return False
        return request.auth.get("purpose") == purpose
