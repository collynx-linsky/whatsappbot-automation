# WhatsApp Integration

`apps.whatsapp` — connects each business's own WhatsApp Business number to
the platform and processes the inbound/outbound message flow from spec
section 9. **No real Meta/WhatsApp credentials were available while
building this** — the whole pipeline is built and tested against a
simulated webhook payload matching Meta's real schema; see
[Testing without real credentials](#testing-without-real-credentials)
below for how to prove it works and what changes the moment you have a
real Meta App.

## Architecture

```text
WhatsApp (Meta)
   |
   v
POST /api/v1/whatsapp/webhook/         <- ONE URL, shared by every
   |  verify X-Hub-Signature-256          business's phone number
   v
apps.whatsapp.services.process_webhook_payload()
   |  parse_webhook_payload()  (apps.whatsapp.providers — normalizes Meta's
   |                            nested JSON into flat event dicts)
   |  resolve WhatsAppAccount by phone_number_id  -> tenant
   |  idempotency check (MessageEvent unique per account+event id)
   |  get_or_create Customer (by phone, within that tenant)
   |  get_or_create open Conversation
   v
apps.messages.Message (sender_type=customer, direction=inbound)
   |
   v  [staff replies via POST /api/v1/messages/, sender_type=staff]
   |
apps.whatsapp.signals.dispatch_outbound_message  (Message post_save)
   v
apps.whatsapp.tasks.send_whatsapp_message_task   (Celery, queue=high_priority)
   v
apps.whatsapp.providers.WhatsAppCloudProvider.send_text_message()
   v
WhatsApp (Meta) — Graph API POST /{phone_number_id}/messages
```

`apps.messages` has **zero import of `apps.whatsapp`** — the dependency
only goes one direction (whatsapp depends on messages, not the reverse),
via a Django signal. This is the concrete instance of the
`MessagingProvider` interface described in `docs/architecture.md`: a
future Telegram or SMS provider app would listen to the same
`Message` `post_save` signal rather than requiring any change to
`apps.messages` or `apps.conversations`.

## Multi-tenant identity resolution

The **only** way a webhook event gets attached to a tenant is by looking
up `WhatsAppAccount.objects.get(phone_number_id=<value from the payload>)`
— the payload's `phone_number_id` is Meta's own identifier for the
business's connected number, not something a client controls, and it only
resolves to a tenant if that exact number was previously connected via
`POST /api/v1/whatsapp/accounts/` by an authenticated manager+ of that
tenant. An unrecognized `phone_number_id` is silently ignored (logged,
`200` still returned to Meta) rather than erroring — this matters because
during initial App setup Meta sends test webhook traffic before any real
account is connected.

## Security

- **Signature verification** (`apps.whatsapp.services.verify_signature`):
  every webhook POST must carry a valid `X-Hub-Signature-256` header — an
  HMAC-SHA256 of the *raw* request body keyed by `WHATSAPP_APP_SECRET`,
  compared with `hmac.compare_digest` (constant-time). Missing app secret
  or invalid signature → `403`, nothing processed. This fails **closed**:
  an unconfigured `WHATSAPP_APP_SECRET` rejects all webhook traffic rather
  than accepting it unsigned.
- **Verify-token handshake** (`GET` on the webhook URL): Meta's one-time
  App-level subscription check, compared against `WHATSAPP_VERIFY_TOKEN`.
  This is platform-level (one Meta App, configured once), unlike the
  per-business credentials below.
- **Access tokens encrypted at rest** (`core.crypto`, Fernet/AES):
  `WhatsAppAccount.access_token_encrypted` is never readable as plaintext
  except via the `.access_token` property, in-process. The API serializer
  (`WhatsAppAccountSerializer`) accepts `access_token` as write-only and
  never includes it (masked or otherwise) in any response — proven by
  `tests/test_whatsapp.py::TestWhatsAppAccountAPI` checking the actual
  rendered HTTP response body, not just the pre-render Python data.
- **Webhook idempotency** (`MessageEvent`, unique per
  `(whatsapp_account, external_event_id)`): Meta redelivers webhooks on
  timeout/error. A duplicate delivery hits the unique constraint inside an
  atomic block and rolls back cleanly — no duplicate `Message`, no partial
  state. Proven live and by test.

## Outbound sending — Celery, not synchronous

Per spec section 26 ("Do not block HTTP requests with long AI/WhatsApp
calls"), `POST /api/v1/messages/` returns immediately with the message in
`PENDING` status; the actual WhatsApp API call happens in
`send_whatsapp_message_task` on the `high_priority` queue.
**Both `scripts/start.ps1` and `docker-compose.yml`'s celery_worker command
were updated to listen on `-Q default,high_priority,low_priority`** —
without that, tasks routed to a non-default queue would silently never run
on a worker started before this phase existed. If a tenant has no
`WhatsAppAccount` with `status=connected`, the task logs and returns
without erring — the message just stays `PENDING` (an honest reflection of
"not actually delivered anywhere," not a lie).

## API

See `docs/api.md` for the full endpoint table. Summary:
`POST /api/v1/whatsapp/accounts/` (manager+, connects a number),
`GET/PATCH /api/v1/whatsapp/accounts/{id}/`, and the webhook itself at
`/api/v1/whatsapp/webhook/` (`GET` for Meta's verification handshake,
`POST` for events — both `AllowAny`, protected by the mechanisms above
instead of JWT since Meta's servers can't carry your platform's tokens).

## Testing without real credentials

Every test in `tests/test_whatsapp.py` runs against a **hand-built payload
matching WhatsApp Cloud API's real webhook JSON shape** (`entry[].changes[].value.messages[]`,
`metadata.phone_number_id`, `contacts[].profile.name`, etc.) with a
correctly-computed HMAC signature — this proves the entire pipeline
(signature check → account lookup → tenant resolution → customer/
conversation/message creation → idempotency) end-to-end without ever
calling Meta. The outbound path is tested by mocking
`apps.whatsapp.providers.requests.post` — no real HTTP call leaves the
machine during tests.

**Also verified live**, beyond the automated tests, against a real
`curl`-driven webhook POST (correct signature accepted; redelivery of the
same event produced `created: 0`, proving idempotency; a tampered
signature got `403`) and — with a genuinely running Redis + a real
`celery worker` process — a real staff reply that was picked up from the
`high_priority` queue and actually sent as an HTTP request to
`graph.facebook.com`, which correctly rejected the dev-only fake access
token and left the message `status=failed`. That's every part of the
pipeline except "the token happens to be valid."

**What changes with real credentials**: nothing in the code — connect a
real WhatsApp Business number via `POST /api/v1/whatsapp/accounts/` with
its real `phone_number_id`/`access_token`/`business_account_id`, point
Meta's App webhook configuration at
`https://<your-domain>/api/v1/whatsapp/webhook/` with the same
`WHATSAPP_VERIFY_TOKEN` and `WHATSAPP_APP_SECRET` from `.env`, and real
traffic flows through the exact same code path the tests exercise.

## Limitations / not built

- Only inbound `text` messages populate real content; `image`/`document`/
  `audio`/`video`/`location` are recorded with the correct `message_type`
  but no caption/media-download handling — media files aren't fetched
  from Meta's temporary media URLs yet.
- Delivery/read status webhook events (Meta sends these under the same
  `changes[].value` shape, without a `messages` key) aren't consumed —
  `Message.status` for outbound messages only reflects our own send
  attempt (`sent`/`failed`), not WhatsApp's delivered/read receipts.
- No "test connection" call to the Graph API when connecting an account —
  credentials are accepted and marked `connected` optimistically; a typo'd
  access token isn't caught until the first real send fails.
- AI/human handoff (spec section 10) isn't built — every inbound message
  simply lands in the conversation for a human to see. `Conversation.ai_enabled`
  is stored but nothing reads it yet (Phase 8).
