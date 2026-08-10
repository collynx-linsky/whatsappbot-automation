"""
WhatsAppBusinessAI — AI Provider Abstraction (spec section 38)

    AIProvider (interface)
     |- OpenAIProvider     <- built
     |- AnthropicProvider  <- built
     \- FutureProvider

Both providers speak plain HTTP (via `requests`, no vendor SDK dependency)
— chat-completion-style, text-only, no streaming/function-calling/vision.
That's the whole surface this MVP needs; see docs/ai.md for what's not
built.

**Confidence is a heuristic, not a calibrated probability.** Neither
OpenAI's nor Anthropic's chat completion APIs return a real confidence
score — computing one properly needs a separate self-evaluation step or
classifier, which is future work. `_estimate_confidence` below just looks
at how the response finished and whether it hedges, and is honest about
being approximate.
"""

import logging
from abc import ABC, abstractmethod
from typing import TypedDict

import requests
from django.conf import settings

logger = logging.getLogger("waba")

_HEDGE_PHRASES = (
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "i cannot help",
    "i can't help",
    "as an ai",
    "i don't have access",
)


class AIReply(TypedDict):
    success: bool
    text: str
    confidence: float
    tokens_used: int
    error: str | None


def _estimate_confidence(text: str, finished_naturally: bool) -> float:
    if not text:
        return 0.0
    if not finished_naturally:
        return 0.5  # truncated — probably fine, but incomplete
    lowered = text.lower()
    if any(phrase in lowered for phrase in _HEDGE_PHRASES):
        return 0.4
    return 0.85


class AIProvider(ABC):
    @abstractmethod
    def generate_reply(
        self, *, system_prompt: str, history: list[dict], user_message: str, max_tokens: int
    ) -> AIReply:
        """
        `history` is a list of {"role": "user"|"assistant", "content": str},
        oldest first — the recent conversation turns, not including
        `user_message` itself (the newest inbound message).
        """


class OpenAIProvider(AIProvider):
    API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, *, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def generate_reply(self, *, system_prompt, history, user_message, max_tokens) -> AIReply:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = requests.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning("OpenAI request failed (network): %s", exc)
            return AIReply(success=False, text="", confidence=0.0, tokens_used=0, error=str(exc))

        data = response.json() if response.content else {}
        if response.status_code >= 400:
            error_message = (data.get("error") or {}).get(
                "message", f"HTTP {response.status_code}"
            )
            logger.warning("OpenAI request failed (API): %s", error_message)
            return AIReply(
                success=False, text="", confidence=0.0, tokens_used=0, error=error_message
            )

        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "").strip()
        finished_naturally = choice.get("finish_reason") == "stop"
        tokens_used = (data.get("usage") or {}).get("total_tokens", 0)

        return AIReply(
            success=True,
            text=text,
            confidence=_estimate_confidence(text, finished_naturally),
            tokens_used=tokens_used,
            error=None,
        )


class AnthropicProvider(AIProvider):
    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"
    DEFAULT_MODEL = "claude-3-5-sonnet-latest"

    def __init__(self, *, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def generate_reply(self, *, system_prompt, history, user_message, max_tokens) -> AIReply:
        messages = list(history) + [{"role": "user", "content": user_message}]

        try:
            response = requests.post(
                self.API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "system": system_prompt,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning("Anthropic request failed (network): %s", exc)
            return AIReply(success=False, text="", confidence=0.0, tokens_used=0, error=str(exc))

        data = response.json() if response.content else {}
        if response.status_code >= 400:
            error_message = (data.get("error") or {}).get(
                "message", f"HTTP {response.status_code}"
            )
            logger.warning("Anthropic request failed (API): %s", error_message)
            return AIReply(
                success=False, text="", confidence=0.0, tokens_used=0, error=error_message
            )

        content_blocks = data.get("content") or []
        text = "".join(
            b.get("text", "") for b in content_blocks if b.get("type") == "text"
        ).strip()
        finished_naturally = data.get("stop_reason") == "end_turn"
        usage = data.get("usage") or {}
        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        return AIReply(
            success=True,
            text=text,
            confidence=_estimate_confidence(text, finished_naturally),
            tokens_used=tokens_used,
            error=None,
        )


def get_provider(name: str, model: str = "") -> AIProvider | None:
    """
    Returns a configured provider instance for `name` (AISettings.Provider's
    value — "openai"/"anthropic"), or None if that provider's API key isn't
    set in .env. Takes a plain string rather than importing
    apps.ai.models.AISettings.Provider to keep this module import-order
    independent of the model layer.
    """
    if name == "openai":
        if not settings.OPENAI_API_KEY:
            return None
        return OpenAIProvider(api_key=settings.OPENAI_API_KEY, model=model)
    if name == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            return None
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=model)
    return None
