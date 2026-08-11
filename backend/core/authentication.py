"""
WhatsAppBusinessAI — Authentication Classes

FullAccessJWTAuthentication is the platform-wide default (see
config/settings/base.py's REST_FRAMEWORK). It refuses to authenticate a
token minted for the MFA setup/challenge flow (apps.accounts.mfa) — those
tokens exist only so a not-yet-fully-authenticated user can call the
specific MFA endpoints that accept them, and must never work anywhere
else.

This is enforced at the authentication layer, not via permission_classes,
because nearly every view in this codebase sets its own explicit
`permission_classes` (overriding DEFAULT_PERMISSION_CLASSES) — a
platform-wide permission-class rule would silently not apply to any of
them. Authentication has no such per-view escape hatch: every request
still goes through DEFAULT_AUTHENTICATION_CLASSES first, regardless of
what permissions a view declares afterward.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class FullAccessJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        if validated_token.get("purpose"):
            raise AuthenticationFailed("This token cannot be used here.", code="mfa_pending_token")
        return super().get_user(validated_token)
