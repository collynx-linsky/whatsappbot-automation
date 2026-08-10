"""
WhatsAppBusinessAI — AI Reply Generation & Human Handoff (spec sections 10, 11)

generate_ai_reply() is the orchestrator: given a fresh inbound customer
Message, decides AI vs. human (spec section 10's trigger list) and either
creates an AI-authored outbound Message or hands the conversation off.
"""

import logging

from apps.businesses.models import Business
from apps.common.models import AuditLog
from apps.messages.models import Message

from .models import AISettings
from .providers import get_provider

logger = logging.getLogger("waba")

# Built-in phrases that mean "let me talk to a person" — separate from
# AISettings.handoff_keywords, which are business-specific additions.
_HUMAN_REQUEST_PHRASES = (
    "talk to a human",
    "speak to a human",
    "human agent",
    "real person",
    "speak to someone",
    "talk to someone",
    "customer care",
    "customer service agent",
)

HISTORY_TURNS = 10


def _get_ai_settings(tenant) -> AISettings | None:
    business = Business.objects.filter(tenant=tenant).first()
    if business is None:
        return None
    return AISettings.objects.filter(business=business).select_related("business").first()


def wants_human(text: str, custom_keywords: list) -> str | None:
    """Returns a human-readable reason string if handoff should trigger, else None."""
    lowered = text.lower()
    for phrase in _HUMAN_REQUEST_PHRASES:
        if phrase in lowered:
            return "customer asked for a human"
    for keyword in custom_keywords:
        if keyword and keyword.lower() in lowered:
            return f"message matched handoff keyword '{keyword}'"
    return None


def build_system_prompt(business, settings_: AISettings) -> str:
    if settings_.system_prompt:
        return settings_.system_prompt

    hours = (
        ", ".join(f"{d}: {h}" for d, h in (business.opening_hours or {}).items())
        or "not specified"
    )
    return (
        f"You are {settings_.assistant_name}, a helpful WhatsApp assistant for "
        f"{business.name}, a {business.get_category_display()} business "
        f"in {business.city or business.country}.\n"
        f"Business description: {business.description or 'not provided'}\n"
        f"Opening hours: {hours}\n"
        f"Currency: {business.currency}\n"
        f"Respond in {settings_.language}. Tone: {settings_.tone}.\n"
        "Only answer using information actually given to you about this business — "
        "never invent prices, stock levels, or facts you don't know; say you're not "
        "sure and offer to connect the customer with a team member instead.\n"
        f"Keep responses under {settings_.max_response_length} characters."
    )


def _recent_history(conversation, exclude_message_id) -> list[dict]:
    messages = (
        conversation.messages.exclude(id=exclude_message_id)
        .exclude(sender_type=Message.SenderType.SYSTEM)
        .order_by("-created_at")[:HISTORY_TURNS]
    )
    history = []
    for message in reversed(list(messages)):
        role = "user" if message.sender_type == Message.SenderType.CUSTOMER else "assistant"
        history.append({"role": role, "content": message.content})
    return history


def _hand_off(conversation, settings_: AISettings, reason: str):
    conversation.ai_enabled = False
    conversation.save(update_fields=["ai_enabled", "updated_at"])

    reply = Message.objects.create(
        tenant=conversation.tenant,
        conversation=conversation,
        sender_type=Message.SenderType.AI,
        direction=Message.Direction.OUTBOUND,
        content=settings_.fallback_message,
        status=Message.Status.PENDING,
    )
    conversation.record_message(reply)

    AuditLog.log(
        action="AI_HANDOFF",
        tenant=conversation.tenant,
        obj=conversation,
        metadata={"reason": reason},
    )
    logger.info("Conversation %s handed off to human: %s", conversation.id, reason)
    return reply


def generate_ai_reply(inbound_message: Message) -> Message | None:
    """
    Given a freshly-created inbound customer Message, generates and stores
    the AI's (or handoff's) reply. Returns the created Message, or None if
    AI is disabled for this conversation/business.
    """
    conversation = inbound_message.conversation
    settings_ = _get_ai_settings(conversation.tenant)

    if settings_ is None or not settings_.ai_enabled or not conversation.ai_enabled:
        return None
    if settings_.mode == AISettings.Mode.HUMAN:
        return None

    handoff_reason = wants_human(inbound_message.content, settings_.handoff_keywords)
    if handoff_reason and settings_.human_handoff_enabled:
        return _hand_off(conversation, settings_, handoff_reason)

    provider = get_provider(settings_.provider, settings_.model_name)
    if provider is None:
        if settings_.human_handoff_enabled:
            return _hand_off(
                conversation, settings_, f"{settings_.provider} API key not configured"
            )
        logger.warning(
            "AI provider '%s' unavailable for tenant %s and handoff is disabled — no reply sent.",
            settings_.provider,
            conversation.tenant_id,
        )
        return None

    business = settings_.business
    system_prompt = build_system_prompt(business, settings_)
    history = _recent_history(conversation, inbound_message.id)

    reply = provider.generate_reply(
        system_prompt=system_prompt,
        history=history,
        user_message=inbound_message.content,
        max_tokens=settings_.max_response_length,
    )

    if not reply["success"] or reply["confidence"] < settings_.confidence_threshold:
        if settings_.human_handoff_enabled:
            reason = reply["error"] or f"low confidence ({reply['confidence']:.2f})"
            return _hand_off(conversation, settings_, reason)
        text = settings_.fallback_message
    else:
        text = reply["text"]

    message = Message.objects.create(
        tenant=conversation.tenant,
        conversation=conversation,
        sender_type=Message.SenderType.AI,
        direction=Message.Direction.OUTBOUND,
        content=text,
        status=Message.Status.PENDING,
    )
    conversation.record_message(message)
    return message
