"""WhatsAppBusinessAI — Development Settings"""

from .base import *  # noqa: F401,F403

DEBUG = True

INSTALLED_APPS += ["django_extensions"]  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # noqa: F405
