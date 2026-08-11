"""WhatsAppBusinessAI — Analytics Views"""

from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsStaffOrAbove, IsSuperAdmin

from . import platform_services, services


def _parse_bound(request, param):
    raw = request.query_params.get(param)
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        raise ValidationError({param: "Must be an ISO 8601 datetime, e.g. 2026-01-01T00:00:00Z."})
    return parsed


class AnalyticsDashboardView(APIView):
    """
    GET /api/v1/analytics/dashboard/ — staff+, the caller's own tenant.
    Optional `?start=&end=` (ISO 8601 datetimes) bound every metric to a
    period; omitted means "all time." See docs/analytics.md for the
    per-business-vs-per-tenant scoping note.
    """

    permission_classes = [IsStaffOrAbove]

    def get(self, request):
        start = _parse_bound(request, "start")
        end = _parse_bound(request, "end")
        return Response(services.business_dashboard(request.user.tenant, start, end))


class PlatformAnalyticsView(APIView):
    """GET /api/v1/analytics/platform/ — super admin only, platform-wide stats."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response(platform_services.platform_dashboard())
