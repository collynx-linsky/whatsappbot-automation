"""
WhatsAppBusinessAI — Embedding Provider Abstraction (spec section 38)

Only OpenAI is implemented: Anthropic has no public embeddings API as of
this writing, so `AISettings.provider == "anthropic"` businesses still get
OpenAI embeddings for retrieval if `OPENAI_API_KEY` is set (embeddings and
chat completion are independent choices — a business's *reply* provider
doesn't have to match its *retrieval* provider). If neither is available,
`get_embedding_provider()` returns `None` and callers fall back to
keyword-only retrieval — same "None means gracefully degrade" contract as
`apps.ai.providers.get_provider`.
"""

import logging
from abc import ABC, abstractmethod

import requests
from django.conf import settings

logger = logging.getLogger("waba")


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Returns one embedding vector per input text, in order, or None on failure."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    API_URL = "https://api.openai.com/v1/embeddings"
    MODEL = "text-embedding-3-small"

    def __init__(self, *, api_key: str):
        self.api_key = api_key

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not texts:
            return []
        try:
            response = requests.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.MODEL, "input": texts},
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning("OpenAI embeddings request failed (network): %s", exc)
            return None

        data = response.json() if response.content else {}
        if response.status_code >= 400:
            error_message = (data.get("error") or {}).get(
                "message", f"HTTP {response.status_code}"
            )
            logger.warning("OpenAI embeddings request failed (API): %s", error_message)
            return None

        # The API guarantees `data` entries come back in the same order as
        # `input`, each carrying its own `index` — sort defensively anyway
        # rather than trust ordering blindly.
        items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in items]


def get_embedding_provider() -> EmbeddingProvider | None:
    if not settings.OPENAI_API_KEY:
        return None
    return OpenAIEmbeddingProvider(api_key=settings.OPENAI_API_KEY)
