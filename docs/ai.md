# AI Engine

`apps.ai` — generates (or hands off) the assistant's reply to every inbound
WhatsApp customer message, per spec sections 10 and 11. **No real
OpenAI/Anthropic API key was available while building this** — the whole
pipeline is built and tested against a mocked HTTP layer for the success
path, and the "no API key configured" handoff path is exercised for real
(genuinely reachable without credentials); see
[Testing without real credentials](#testing-without-real-credentials) below.

## Architecture

```text
apps.messages.Message (sender_type=customer, direction=inbound)
   |  post_save signal
   v
apps.ai.signals.dispatch_ai_reply
   v
apps.ai.tasks.generate_ai_response_task   (Celery, queue=default)
   v
apps.ai.services.generate_ai_reply()
   |
   |-- AI disabled (business or conversation) or mode=human -> return, no reply
   |
   |-- wants_human() matches a built-in phrase or a business handoff_keyword?
   |     yes -> _hand_off()  (skips the provider call entirely)
   |
   |-- get_provider(settings.provider, settings.model_name)
   |     None (no API key configured) -> _hand_off() if human_handoff_enabled,
   |                                      else log + no reply
   |
   |-- provider.generate_reply(system_prompt, history, user_message)
   |     failed, or confidence < confidence_threshold
   |       -> _hand_off() if human_handoff_enabled, else send fallback_message
   |     succeeded
   |       -> create AI-authored outbound Message
   v
apps.messages.Message (sender_type=ai, direction=outbound)
   |  post_save signal
   v
apps.whatsapp.signals.dispatch_outbound_message   (STAFF and AI messages both sendable)
   v
apps.whatsapp.tasks.send_whatsapp_message_task   -> WhatsApp (Meta)
```

Same decoupling pattern as `docs/whatsapp.md`: `apps.messages` has **zero
import of `apps.ai`** — the connection is one-directional via the
`Message.post_save` signal, and a future non-AI auto-responder would plug
in the same way. `apps.whatsapp.signals._SENDABLE_SENDER_TYPES` was
extended from `(STAFF,)` to `(STAFF, AI)` so an AI-authored reply actually
reaches the customer, not just a human-typed one; `SYSTEM`-type messages
(reserved for future internal notes) deliberately still never send.

## AI vs. human handoff decision (spec section 10)

Checked in this order, cheapest first — the keyword/phrase check runs
*before* any provider HTTP call, saving a real API call (and cost) when a
human is obviously wanted:

1. **`AISettings.mode == "human"`** — AI never replies at all; every
   inbound message just sits in the conversation for staff, same as before
   this phase existed.
2. **Built-in "talk to a human" phrases** (`apps.ai.services._HUMAN_REQUEST_PHRASES`)
   or a business-defined `handoff_keywords` entry (case-insensitive
   substring match) appears in the message.
3. **No provider configured** for `AISettings.provider` — i.e. the
   relevant `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` is blank in `.env`.
4. **The provider call itself failed** (network error or a non-2xx API
   response).
5. **Confidence below `AISettings.confidence_threshold`** (default `0.6`)
   — see [Confidence scoring](#confidence-scoring-a-heuristic-not-a-probability)
   below for why this is explicitly a heuristic.

In every handoff case: `Conversation.ai_enabled` is set to `False` (so
follow-up inbound messages on the *same* conversation don't keep
re-triggering AI attempts until a human manually flips it back via the
API), `AISettings.fallback_message` is sent to the customer as a normal
AI-authored message (the handoff is invisible to them — they just get a
graceful "let me get someone to help you" reply, not silence), and an
`AuditLog` row is written (`action="AI_HANDOFF"`, `metadata={"reason": ...}`)
so a business owner can later see *why* a given conversation was handed
off. If `human_handoff_enabled` is `False` and there's simply no reply to
send (no provider, or a failed call), nothing is sent and the event is
only logged server-side — silence, not a broken-looking auto-reply.

## Provider abstraction (spec section 38)

`AIProvider` (interface) → `OpenAIProvider` / `AnthropicProvider`, both
speaking plain HTTP via `requests` (no vendor SDK dependency, matching
`apps.whatsapp.providers`'s pattern) — chat-completion-style, text-only, no
streaming/function-calling/vision. `get_provider(name, model)` returns
`None` rather than raising when the matching API key isn't set in `.env`,
which is exactly the signal `generate_ai_reply` uses to hand off instead of
erroring.

## Confidence scoring: a heuristic, not a probability

Neither OpenAI's nor Anthropic's chat completion APIs return a real
confidence score — computing a calibrated one needs a separate
self-evaluation step or classifier, which is future work, not built here.
`apps.ai.providers._estimate_confidence` is an honestly-labeled
approximation: `0.0` for an empty response, `0.5` if the response was
truncated (`finish_reason`/`stop_reason` wasn't a natural stop), `0.4` if
the text contains a hedge phrase ("I'm not sure", "I don't know", ...),
`0.85` otherwise. Do not treat this as a real probability anywhere else in
the codebase.

## System prompt

If `AISettings.system_prompt` is blank (the default), `build_system_prompt`
constructs one from the business's own profile — name, category, city/
country, description, opening hours, currency — with an explicit
instruction to **never invent prices, stock levels, or facts it doesn't
know**, and to offer a human handoff instead of guessing. This directly
implements the master spec's grounding requirement; a business can still
override it entirely with a custom `system_prompt`.

## Conversation history

`apps.ai.services._recent_history` sends the AI provider the last 10
non-`SYSTEM` messages in the conversation (oldest first, `role: user` for
customer messages, `role: assistant` for staff/AI messages) as context —
capped to bound both the request size and cost per reply.

## API

See `docs/api.md` for the full endpoint table. Summary:
`GET/PATCH /api/v1/ai/settings/` (manager+, singleton-per-tenant — created
lazily with model defaults on first request) and
`POST /api/v1/ai/test/` (manager+, the onboarding "test your AI" step —
runs the same handoff-check + prompt-building logic against ad-hoc text,
without creating a real `Conversation`/`Message`).

## Testing without real credentials

`tests/test_ai.py` mocks `apps.ai.providers.requests.post` for every
success-path assertion (a real HTTP call never leaves the machine during
tests) and tests the "no API key configured" handoff path directly — that
one is genuinely reachable without credentials, since `get_provider`
returns `None` whenever `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` is blank, so
no mocking is needed to prove it works. Provider selection, keyword/phrase
handoff detection, mode gating, confidence-threshold handoff, and tenant
isolation + RBAC on both endpoints are all covered.

**Also verified live**: logged in as a real seeded business owner against
a running dev server (no API key configured), `GET /api/v1/ai/settings/`
correctly lazily-created and returned default settings, and
`POST /api/v1/ai/test/` correctly reported `{"handed_off": true, "reason":
"openai API key not configured"}` — a real, honest failure, not a
simulated one. Tenant isolation (a second business owner gets their own
settings, never the first's) and RBAC (a `staff`-role account gets `403`
on `PATCH /api/v1/ai/settings/`) were both proven against the live server
too, not just unit tests.

**What changes with real credentials**: nothing in the code — set
`OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`, and point `AISettings.provider`
at it) in `.env`, and the exact same code path that currently hands off
starts generating real replies instead.

## Limitations / not built

- Confidence scoring is a heuristic (see above), not a calibrated
  probability — don't rely on the exact threshold value meaning anything
  beyond "roughly how hedgy/complete the response looked."
- No streaming, function-calling/tool-use, or vision — text-only,
  single-shot completions.
- No RAG grounding yet — the system prompt is built from the business's
  own profile fields only; retrieving from an uploaded knowledge base
  (product catalogs, FAQs, policy documents) is Phase 9
  (`apps.knowledge`), not this phase.
- `POST /api/v1/ai/test/` has no rate limiting yet — an unthrottled loop
  against it would burn real provider quota/cost once a key is configured.
  Flagged in `docs/security.md`, tracked as Phase 15 work.
- No per-tenant AI usage/cost tracking (tokens used, message count) —
  `AIReply["tokens_used"]` is computed by each provider but currently
  discarded by `generate_ai_reply`, not persisted anywhere. Billing/usage
  enforcement is Phase 13 (`apps.billing`).
- `AISettings.handoff_keywords` is a plain JSON list of strings — no UI
  validation for near-duplicate/overlapping keywords, no per-keyword
  case sensitivity option.
