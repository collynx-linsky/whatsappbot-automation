"""WhatsAppBusinessAI — Production Settings"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# Encrypted DB connections, not just encrypted-at-rest fields (core.crypto)
# — "require" refuses to connect at all over a plaintext channel. Override
# to "verify-full" (with the provider's CA cert configured) for the
# strongest guarantee once a real production Postgres host is chosen.
DATABASES["default"]["OPTIONS"]["sslmode"] = env(  # noqa: F405
    "POSTGRES_SSLMODE", default="require"
)

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
# Both already match Django 5.2's own global defaults — made explicit
# here so a future Django upgrade changing its defaults can't silently
# change this app's behavior without it showing up as a diff.
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
