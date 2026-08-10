"""WhatsAppBusinessAI — Campaigns Views"""

from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.mixins import TenantScopedQuerysetMixin
from core.permissions import IsManagerOrAbove, IsStaffOrAbove

from .models import Campaign, CampaignRecipient, MessageTemplate, Segment
from .serializers import (
    CampaignRecipientSerializer,
    CampaignSerializer,
    MessageTemplateSerializer,
    SegmentPreviewSerializer,
    SegmentSerializer,
)
from .services import get_segment_customers


class _CreatedByMixin:
    """Like core.mixins.TenantScopedCreateMixin, but also stamps `created_by` —
    every model in this app tracks who created it, unlike most other tenant-scoped apps."""

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if tenant is None:
            raise ValidationError(
                "A super admin has no tenant of their own and cannot create this directly."
            )
        serializer.save(tenant=tenant, created_by=self.request.user)


class MessageTemplateListCreateView(
    TenantScopedQuerysetMixin, _CreatedByMixin, generics.ListCreateAPIView
):
    """GET (staff+) / POST (manager+) /api/v1/campaigns/templates/"""

    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.select_related("business", "created_by").all()
    filterset_fields = ["status", "category"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class MessageTemplateDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """
    GET (staff+) / PATCH (manager+) /api/v1/campaigns/templates/{id}/

    `status`/`whatsapp_template_name`/`rejection_reason` are writable here
    deliberately — Meta approval happens outside this system (no real
    credentials this session; see docs/campaigns.md), so a manager records
    the outcome manually once they've checked Meta Business Manager.
    """

    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.select_related("business", "created_by").all()

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class SegmentListCreateView(
    TenantScopedQuerysetMixin, _CreatedByMixin, generics.ListCreateAPIView
):
    """GET (staff+) / POST (manager+) /api/v1/campaigns/segments/"""

    serializer_class = SegmentSerializer
    queryset = Segment.objects.select_related("business", "created_by").all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class SegmentDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET (staff+) / PATCH, DELETE (manager+) /api/v1/campaigns/segments/{id}/"""

    serializer_class = SegmentSerializer
    queryset = Segment.objects.select_related("business", "created_by").all()

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class SegmentPreviewView(TenantScopedQuerysetMixin, generics.GenericAPIView):
    """GET /api/v1/campaigns/segments/{id}/preview/ — staff+, no side effects."""

    permission_classes = [IsStaffOrAbove]
    queryset = Segment.objects.all()

    def get(self, request, *args, **kwargs):
        segment = self.get_object()
        customers = get_segment_customers(segment)
        payload = {
            "customer_count": customers.count(),
            "sample": [
                {"id": str(c.id), "name": c.name, "phone": c.phone} for c in customers[:10]
            ],
        }
        return Response(SegmentPreviewSerializer(payload).data)


class CampaignListCreateView(
    TenantScopedQuerysetMixin, _CreatedByMixin, generics.ListCreateAPIView
):
    """GET (staff+) / POST (manager+) /api/v1/campaigns/"""

    serializer_class = CampaignSerializer
    queryset = Campaign.objects.select_related(
        "business", "segment", "template", "created_by"
    ).all()
    filterset_fields = ["status"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class CampaignDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """
    GET (staff+) / PATCH (manager+) /api/v1/campaigns/{id}/

    PATCH only makes sense while `status=draft` — the model layer doesn't
    block editing a sent campaign's `name`, but there's nothing meaningful
    to change about a campaign that already went out; `segment`/`template`
    changes after sending would misrepresent what was actually sent, so
    the serializer's read_only fields intentionally exclude counts/status
    from being client-writable at all (see CampaignSerializer).
    """

    serializer_class = CampaignSerializer
    queryset = Campaign.objects.select_related(
        "business", "segment", "template", "created_by"
    ).all()

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsManagerOrAbove()]
        return [IsStaffOrAbove()]


class CampaignSendView(TenantScopedQuerysetMixin, generics.GenericAPIView):
    """POST /api/v1/campaigns/{id}/send/ — manager+, queues the actual send."""

    permission_classes = [IsManagerOrAbove]
    queryset = Campaign.objects.all()

    def post(self, request, *args, **kwargs):
        campaign = self.get_object()
        if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED):
            raise ValidationError(
                f"Campaign is '{campaign.status}' — only a draft or scheduled campaign can be sent."
            )

        # Mark scheduled *before* enqueueing, then re-fetch after — under
        # CELERY_TASK_ALWAYS_EAGER (tests) the task runs synchronously
        # inside .delay() and can already have moved the campaign to
        # sent/failed by the time this line returns; saving our stale
        # in-memory "scheduled" over that would silently overwrite the
        # real outcome.
        campaign.status = Campaign.Status.SCHEDULED
        campaign.save(update_fields=["status", "updated_at"])

        from .tasks import send_campaign_task

        send_campaign_task.delay(str(campaign.id))
        campaign.refresh_from_db()
        return Response(CampaignSerializer(campaign).data)


class CampaignRecipientsView(generics.ListAPIView):
    """GET /api/v1/campaigns/{id}/recipients/ — staff+, per-customer send outcome."""

    permission_classes = [IsStaffOrAbove]
    serializer_class = CampaignRecipientSerializer

    def get_queryset(self):
        from django.shortcuts import get_object_or_404

        user = self.request.user
        campaigns = Campaign.objects.all()
        if not user.is_superuser:
            campaigns = campaigns.filter(tenant_id=user.tenant_id)
        campaign = get_object_or_404(campaigns, pk=self.kwargs["pk"])
        return CampaignRecipient.objects.filter(campaign=campaign).select_related("customer")
