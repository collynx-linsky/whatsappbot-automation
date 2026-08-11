"""WhatsAppBusinessAI — WhatsApp Views"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.mixins import TenantScopedCreateMixin, TenantScopedQuerysetMixin
from core.permissions import IsManagerOrAbove

from .models import WhatsAppAccount
from .serializers import WhatsAppAccountSerializer
from .services import process_webhook_payload, verify_signature

logger = logging.getLogger("waba")


class WhatsAppAccountListCreateView(
    TenantScopedQuerysetMixin, TenantScopedCreateMixin, generics.ListCreateAPIView
):
    """GET/POST /api/v1/whatsapp/accounts/ — manager+ (connecting WhatsApp is an admin action)."""

    permission_classes = [IsManagerOrAbove]
    serializer_class = WhatsAppAccountSerializer
    queryset = WhatsAppAccount.objects.select_related("business").all()

    def perform_create(self, serializer):
        from apps.billing.services import check_limit

        check_limit(self.request.user.tenant, "whatsapp_accounts")
        super().perform_create(serializer)


class WhatsAppAccountDetailView(TenantScopedQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/whatsapp/accounts/{id}/"""

    permission_classes = [IsManagerOrAbove]
    serializer_class = WhatsAppAccountSerializer
    queryset = WhatsAppAccount.objects.select_related("business").all()


class WhatsAppWebhookView(APIView):
    """
    /api/v1/whatsapp/webhook/ — the single platform-wide webhook Meta
    calls for every business's phone number registered under this app.
    (No explicit csrf_exempt needed — DRF's APIView.as_view() already
    applies it to every view.)

    GET: Meta's one-time subscription verification handshake
    (hub.mode=subscribe, hub.verify_token, hub.challenge).

    POST: actual message/status events. Verified via X-Hub-Signature-256
    (never trust an unsigned payload) and processed idempotently.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge", "")

        if (
            mode == "subscribe"
            and token
            and settings.WHATSAPP_VERIFY_TOKEN
            and token == settings.WHATSAPP_VERIFY_TOKEN
        ):
            return HttpResponse(challenge, content_type="text/plain")

        logger.warning("WhatsApp webhook verification failed (mode=%s).", mode)
        return HttpResponse(status=403)

    def post(self, request):
        signature = request.META.get("HTTP_X_HUB_SIGNATURE_256")
        if not verify_signature(request.body, signature):
            logger.warning("WhatsApp webhook signature verification failed.")
            return HttpResponse(status=403)

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HttpResponse(status=400)

        created = process_webhook_payload(payload)
        # Meta expects a fast 200 regardless of what we did with it —
        # returning anything else risks Meta disabling the webhook
        # subscription after repeated non-200s.
        return JsonResponse({"received": True, "created": created})
