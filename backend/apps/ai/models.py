"""
WhatsAppBusinessAI — AI Engine Models

AISettings per spec section 11 — one row per business, configuring how
that business's AI assistant behaves. `mode` implements spec section 10's
AI/HUMAN/HYBRID modes; `handoff_keywords` implements the business-defined
keyword trigger.
"""

from django.db import models

from core.models import BaseModel


class AISettings(BaseModel):
    class Mode(models.TextChoices):
        AI = "ai", "AI-only"
        HUMAN = "human", "Human-only"
        HYBRID = "hybrid", "Hybrid (AI with handoff)"

    class Tone(models.TextChoices):
        FRIENDLY = "friendly", "Friendly"
        PROFESSIONAL = "professional", "Professional"
        CASUAL = "casual", "Casual"
        FORMAL = "formal", "Formal"

    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        ANTHROPIC = "anthropic", "Anthropic"

    business = models.OneToOneField(
        "businesses.Business", on_delete=models.CASCADE, related_name="ai_settings"
    )

    assistant_name = models.CharField(max_length=100, default="Assistant")
    system_prompt = models.TextField(
        blank=True,
        help_text="If blank, a default prompt is built from the business's own profile at reply time.",
    )
    language = models.CharField(max_length=10, default="en")
    tone = models.CharField(max_length=20, choices=Tone.choices, default=Tone.FRIENDLY)
    welcome_message = models.TextField(blank=True)
    fallback_message = models.TextField(
        default="I'm not sure about that — let me get a member of our team to help you."
    )
    max_response_length = models.PositiveIntegerField(default=500)

    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.HYBRID)
    ai_enabled = models.BooleanField(default=True)
    human_handoff_enabled = models.BooleanField(default=True)
    confidence_threshold = models.FloatField(
        default=0.6, help_text="Below this, hand off to a human even if human_handoff_enabled."
    )
    handoff_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Case-insensitive substrings — a customer message containing any of these forces handoff.",
    )

    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.OPENAI)
    model_name = models.CharField(
        max_length=100, blank=True, help_text="If blank, a sensible per-provider default is used."
    )

    class Meta:
        db_table = "ai_settings"
        indexes = [models.Index(fields=["tenant"])]

    def __str__(self):
        return f"AI settings for {self.business.name}"

    DEFAULT_HANDOFF_KEYWORDS = [
        "human",
        "agent",
        "representative",
        "manager",
        "speak to someone",
        "refund",
        "complaint",
        "cancel my order",
    ]
