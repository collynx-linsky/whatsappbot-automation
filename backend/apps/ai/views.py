"""WhatsAppBusinessAI — AI Views"""

import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.businesses.models import Business
from core.permissions import IsManagerOrAbove

from .models import AISettings
from .providers import get_provider
from .serializers import AISettingsSerializer, AITestResponseSerializer, AITestSerializer
from .services import append_knowledge_context, build_system_prompt, wants_human

logger = logging.getLogger("waba")


def _get_or_create_settings(tenant) -> AISettings | None:
    """
    One AISettings row per business, created lazily with model defaults the
    first time anyone looks. Returns None if the tenant has no business yet
    (shouldn't happen post-onboarding, but the tenant-scoped views below
    have to handle a caller mid-onboarding gracefully rather than 500).
    """
    business = Business.objects.filter(tenant=tenant).first()
    if business is None:
        return None
    settings_, _ = AISettings.objects.get_or_create(business=business, defaults={"tenant": tenant})
    return settings_


class AISettingsView(APIView):
    """
    GET/PATCH /api/v1/ai/settings/ — the caller's own business's AI
    configuration (spec section 11). Singleton-per-tenant: no id needed in
    the URL, unlike every other tenant-scoped resource in this API.
    """

    permission_classes = [IsManagerOrAbove]

    def get(self, request):
        settings_ = _get_or_create_settings(request.user.tenant)
        if settings_ is None:
            return Response({"detail": "No business found for this tenant yet."}, status=404)
        return Response(AISettingsSerializer(settings_).data)

    def patch(self, request):
        settings_ = _get_or_create_settings(request.user.tenant)
        if settings_ is None:
            return Response({"detail": "No business found for this tenant yet."}, status=404)
        serializer = AISettingsSerializer(
            settings_, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from apps.common.models import AuditLog

        AuditLog.log(
            action="AI_SETTINGS_UPDATED",
            user=request.user,
            tenant=request.user.tenant,
            obj=settings_,
            metadata={"changed_fields": list(request.data.keys())},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(serializer.data)


class AITestView(APIView):
    """
    POST /api/v1/ai/test/ — onboarding step 7 "test your AI": runs the same
    handoff-check + prompt-building logic as a real inbound message, but
    against ad-hoc text and without touching Conversation/Message at all.

    Throttled (`throttle_scope`, see settings.REST_FRAMEWORK) on top of
    the global per-user rate — an unthrottled loop here would burn real
    provider API quota/cost once a key is configured. See docs/security.md.
    """

    permission_classes = [IsManagerOrAbove]
    throttle_scope = "ai_test"

    def post(self, request):
        input_serializer = AITestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        text = input_serializer.validated_data["message"]

        settings_ = _get_or_create_settings(request.user.tenant)
        if settings_ is None:
            return Response({"detail": "No business found for this tenant yet."}, status=404)

        handoff_reason = wants_human(text, settings_.handoff_keywords)
        if handoff_reason and settings_.human_handoff_enabled:
            payload = {"handed_off": True, "reason": handoff_reason}
            return Response(AITestResponseSerializer(payload).data)

        provider = get_provider(settings_.provider, settings_.model_name)
        if provider is None:
            payload = {
                "handed_off": True,
                "reason": f"{settings_.provider} API key not configured",
            }
            return Response(AITestResponseSerializer(payload).data)

        system_prompt = build_system_prompt(settings_.business, settings_)
        system_prompt = append_knowledge_context(system_prompt, settings_.business, text)
        reply = provider.generate_reply(
            system_prompt=system_prompt,
            history=[],
            user_message=text,
            max_tokens=settings_.max_response_length,
        )

        if not reply["success"] or reply["confidence"] < settings_.confidence_threshold:
            reason = reply["error"] or f"low confidence ({reply['confidence']:.2f})"
            payload = {"handed_off": True, "reason": reason}
            return Response(AITestResponseSerializer(payload).data)

        payload = {
            "handed_off": False,
            "reply": reply["text"],
            "confidence": reply["confidence"],
        }
        return Response(AITestResponseSerializer(payload).data)
