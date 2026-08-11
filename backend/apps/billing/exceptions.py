"""WhatsAppBusinessAI — Billing Exceptions"""

from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_402_PAYMENT_REQUIRED


class PlanLimitExceeded(APIException):
    """
    Raised when an action would exceed the tenant's current Plan limit.
    402 Payment Required is the semantically correct status here — this
    isn't "you're not allowed" (403) or "bad input" (400), it's "your
    current plan doesn't cover this; upgrade to continue."
    """

    status_code = HTTP_402_PAYMENT_REQUIRED
    default_code = "plan_limit_exceeded"
