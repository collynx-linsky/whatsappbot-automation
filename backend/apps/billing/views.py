"""WhatsAppBusinessAI — Billing Views"""

import datetime

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import TenantScopedQuerysetMixin
from core.permissions import IsManagerOrAbove, IsStaffOrAbove, IsSuperAdmin

from .models import Invoice
from .serializers import GenerateInvoiceSerializer, InvoiceSerializer
from .services import generate_invoice, usage_summary


class UsageSummaryView(APIView):
    """GET /api/v1/billing/usage/ — staff+, the caller's own tenant's usage vs. Plan limits."""

    permission_classes = [IsStaffOrAbove]

    def get(self, request):
        return Response(usage_summary(request.user.tenant))


class InvoiceListView(TenantScopedQuerysetMixin, generics.ListAPIView):
    """GET /api/v1/billing/invoices/ — manager+, the caller's own tenant's billing history."""

    permission_classes = [IsManagerOrAbove]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all()


class InvoiceDetailView(TenantScopedQuerysetMixin, generics.RetrieveAPIView):
    """GET /api/v1/billing/invoices/{id}/ — manager+, 404 if in another tenant."""

    permission_classes = [IsManagerOrAbove]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all()


class GenerateInvoiceView(APIView):
    """
    POST /api/v1/billing/invoices/generate/ — super admin only. Manually
    triggers invoice generation for one tenant (no automated payment
    gateway/webhook exists to trigger this — see docs/billing.md).
    `{tenant, period_start?}` — `period_start` defaults to the current
    calendar month's first day.
    """

    permission_classes = [IsSuperAdmin]

    def post(self, request):
        from .services import current_month_start

        serializer = GenerateInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.validated_data["tenant"]
        period_start = serializer.validated_data.get("period_start") or current_month_start()
        # Last day of period_start's month, without a calendar library:
        # jump to day 28 (always valid), add 4 days (always rolls into
        # next month), snap to day 1, step back one day.
        next_month = (period_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        period_end = next_month - datetime.timedelta(days=1)

        invoice = generate_invoice(tenant, period_start, period_end)
        if invoice is None:
            return Response(
                {"detail": "This tenant has no plan assigned — cannot generate an invoice."},
                status=400,
            )
        return Response(InvoiceSerializer(invoice).data, status=201)
