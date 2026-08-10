"""
WhatsAppBusinessAI — Custom Exception Handling
Standardizes all API error responses into a single envelope.
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, NotAuthenticated
from rest_framework.exceptions import NotFound as DRFNotFound
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("waba")


def custom_exception_handler(exc, context):
    """
    Wraps every API error in a consistent envelope:
    {"status": "error", "message": "...", "errors": {...}, "code": "..."}
    """
    if isinstance(exc, Http404):
        exc = DRFNotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied()

    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "status": "error",
            "message": _get_message(exc),
            "errors": _format_errors(response.data),
            "code": _get_error_code(exc),
        }
    else:
        logger.exception("Unhandled exception in API view", exc_info=exc)
        response = Response(
            {
                "status": "error",
                "message": "An unexpected error occurred. Please try again.",
                "errors": {},
                "code": "internal_server_error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _get_message(exc) -> str:
    if isinstance(exc, ValidationError):
        return "Validation failed. Please check the submitted data."
    if isinstance(exc, NotAuthenticated):
        return "Authentication credentials were not provided."
    if isinstance(exc, AuthenticationFailed):
        return "Invalid authentication credentials."
    if isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this action."
    if hasattr(exc, "detail"):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and len(detail) > 0:
            return str(detail[0])
    return str(exc)


def _get_error_code(exc) -> str:
    if hasattr(exc, "default_code"):
        return exc.default_code
    return type(exc).__name__.lower()


def _format_errors(data) -> dict:
    if isinstance(data, dict):
        return {
            k: [str(v) for v in vals] if isinstance(vals, list) else [str(vals)]
            for k, vals in data.items()
        }
    if isinstance(data, list):
        return {"non_field_errors": [str(item) for item in data]}
    return {"detail": [str(data)]}


# ── Custom Exceptions ─────────────────────────────────────────


class WABAException(APIException):
    """Base exception for the platform."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A platform error occurred."
    default_code = "waba_error"


class TenantNotFound(WABAException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Tenant not found or inactive."
    default_code = "tenant_not_found"


class TenantSuspended(WABAException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "This account has been suspended."
    default_code = "tenant_suspended"


class SubscriptionLimitExceeded(WABAException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "This action exceeds your current plan's limits."
    default_code = "subscription_limit_exceeded"


class DuplicateRecordError(WABAException):
    default_detail = "A record with this data already exists."
    default_code = "duplicate_record"
