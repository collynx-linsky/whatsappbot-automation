# Marketing Campaigns

`apps.campaigns` — lets a business define a customer Segment, an approved
message Template, and send a bulk Campaign to everyone in that segment,
per spec sections 12 and 26. **No real Meta credentials were available
while building this** (same constraint as every other provider-touching
phase this session) — the whole pipeline is built and tested against a
mocked WhatsApp HTTP layer for the send-success/failure paths, and the
structural-failure paths (no approved template, no connected WhatsApp
account, no opted-in recipients) are exercised for real, since they're
genuinely reachable without credentials.

**Compliance is this app's actual purpose, not a checkbox.** WhatsApp
Business Platform policy is unambiguous on two points, and both are
enforced structurally here — not left to a developer to remember:

1. A business may only send **marketing** messages to customers who have
   **explicitly opted in**. Starting a WhatsApp conversation is not
   opt-in.
2. A business may only send messages **proactively** (i.e. not as a reply
   within an existing 24-hour customer service window) using a
   **pre-approved message template** — free-form text is not allowed for
   this.

## Architecture

```text
Segment.filters (statuses/sources/tags)
   v
apps.campaigns.services.get_segment_customers()
   |  ALWAYS filters marketing_opt_in=True — a Segment's own customer
   |  count can never overstate who can actually be messaged
   v
POST /api/v1/campaigns/  {segment, template, template_variables}
   v
Campaign (status=draft)
   |  POST /api/v1/campaigns/{id}/send/  (manager+)
   v
Campaign (status=scheduled) -> Celery task, queue=low_priority
   v
apps.campaigns.services.send_campaign()
   |-- template.status != approved?           -> FAIL the whole campaign
   |-- no WhatsAppAccount(status=connected)?   -> FAIL the whole campaign
   |-- prepare_campaign_recipients()           -> snapshot segment onto CampaignRecipient[]
   |-- no PENDING recipients?                  -> FAIL the whole campaign
   |
   `-- for each recipient:
         re-check marketing_opt_in (may have changed since scheduling)
           not opted in -> SKIPPED, no send attempted
           opted in     -> WhatsAppCloudProvider.send_template_message()
                            (never send_text_message — see below)
                            -> apps.messages.Message (sender_type=campaign)
                            -> CampaignRecipient.status = sent | failed
   v
Campaign (status=sent, sent_count/failed_count/skipped_count populated)
```

A per-recipient provider failure (bad token, invalid number, rate limit)
only fails **that recipient** — the rest of the batch still goes out, and
the campaign's own `status` still ends at `sent` (it was genuinely
attempted). Only the four structural problems above fail the whole
campaign before any send is attempted.

## Why `send_template_message` is a separate provider method

`apps.whatsapp.providers.MessagingProvider` already had `send_text_message`
(Phase 7, used for staff replies and AI replies — both happen inside an
active customer-initiated conversation). Campaign sends are the opposite
case: proactive, outside any session window, to potentially many
customers who haven't messaged recently. Reusing `send_text_message` with
formatted text would silently violate WhatsApp's own policy (Meta's API
itself would likely reject an unapproved proactive text send outside the
24-hour window, but this codebase shouldn't rely on the remote API to be
the only thing enforcing that). `send_template_message` builds the
correct `{"type": "template", "template": {"name", "language", "components"}}`
payload shape instead — see `apps.whatsapp.providers.WhatsAppCloudProvider
.send_template_message`.

## Message templates: manually-tracked approval, not queried live

`MessageTemplate.status` (`draft → pending_approval → approved/rejected`)
is set **manually** by whoever actually submitted and got the template
approved in Meta's real Business Manager / Template API — this project
has no real Meta credentials to call that API and check status live. A
`Campaign` can only be sent (`send_campaign`) once its template's status
is `approved`; this is checked at send time, not just at campaign-creation
time, so a template that gets rejected after a campaign was drafted
against it correctly blocks that campaign rather than silently sending
something Meta would reject anyway.

## Segments: dynamic filters, snapshotted at send time

A `Segment` stores `filters` (a small JSON dict — `statuses`, `sources`,
`tags`, all any-match lists; empty means "every opted-in customer") and
is **re-evaluated live** every time it's read (list view, preview
endpoint, `customer_count`). A `Campaign`, however, **snapshots** its
segment's customers onto `CampaignRecipient` rows the moment it's sent
(`prepare_campaign_recipients`) — so "who received this campaign" is a
permanent historical record, not something that silently changes if the
segment's underlying customers change later. `marketing_opt_in` is
re-checked a second time at actual send time regardless (see Architecture
above), since a customer can opt out between scheduling and sending.

## API

See `docs/api.md` for the full endpoint table. Summary:
`GET/POST /api/v1/campaigns/templates/`, `GET/PATCH .../templates/{id}/`
(status/approval recorded manually here), `GET/POST /api/v1/campaigns/segments/`,
`GET/PATCH/DELETE .../segments/{id}/`, `GET .../segments/{id}/preview/`
(no side effects — live count + a 10-customer sample), `GET/POST
/api/v1/campaigns/`, `GET/PATCH /api/v1/campaigns/{id}/`, `POST
.../{id}/send/` (manager+, only from `draft`/`scheduled`), `GET
.../{id}/recipients/` (per-customer send outcome).

## Testing without real credentials

`tests/test_campaigns.py` mocks `apps.whatsapp.providers.requests.post`
for send success/failure assertions (and checks the actual outbound HTTP
payload used `type: template`, not free text — proving the compliance
mechanism, not just that *a* message was sent), and tests every
structural-failure path directly since they're genuinely reachable
without credentials: no approved template, no connected WhatsApp account,
zero opted-in recipients. Also covers segment filter evaluation
(status/source/tag any-match, opt-in enforcement), snapshot idempotency,
the mid-flight opt-out case (opted in when scheduled, opted out before
the send actually runs — correctly skipped, provider never called), and
the full API surface (tenant isolation, RBAC, cross-business
segment/template rejection on campaign creation).

**Real bug caught by this testing, not by review, and fixed**:
`CampaignSendView.post` originally set `campaign.status = SCHEDULED` and
saved it **after** calling `send_campaign_task.delay(...)` — under
`CELERY_TASK_ALWAYS_EAGER` (tests, and this bit would be latent but real
under any synchronous task execution) the task had already run to
completion and set the real outcome (`sent`/`failed`) by the time
`.delay()` returned, and the stale in-memory `campaign` object then
overwrote that real outcome back to `scheduled` on save. Fixed by saving
`scheduled` **before** enqueueing, then refreshing from the database
after, so the response always reflects whatever actually happened.

**Also verified live**: seeded segment (`Opted-in customers`) correctly
reports `customer_count: 1` against the one seeded opted-in customer;
attempting to send the seeded draft campaign against a running dev server
correctly queued it (no worker running, so it stayed `scheduled` — same
async-queue reality documented in `docs/rag.md`); directly re-invoking
`send_campaign()` against that live campaign confirmed the real
structural-failure path (`"No connected WhatsApp account for this
business."`) end-to-end against the real Postgres database. Tenant
isolation (`404` on another tenant's template) and RBAC (`403` for
`staff` attempting to create a template) both verified live with two real
seeded business owners.

## Limitations / not built

- No per-recipient personalization — `Campaign.template_variables` is one
  positional list applied identically to every recipient. A future phase
  could support per-customer variable substitution (e.g. `{{1}}` = each
  customer's own name) via a mapping instead of a flat list.
- No scheduling for a future date/time — `Campaign.scheduled_at` exists on
  the model but nothing reads it yet; `POST .../send/` always sends (or
  queues to send) immediately. A `celery beat` periodic task checking for
  due `scheduled_at` campaigns is the natural next step.
- No campaign cancellation endpoint — `Campaign.Status.CANCELLED` exists
  as a choice but nothing transitions to it yet.
- No rate limiting on `POST /api/v1/campaigns/{id}/send/` — flagged in
  `docs/security.md`.
- `Plan.max_campaigns_per_month` exists on the `Plan` model (seeded since
  the Foundation phase) but isn't enforced anywhere yet — real limit
  enforcement is Phase 13 (`apps.billing`) territory, same gap as every
  other `Plan` limit.
- No unsubscribe/opt-out link or keyword handling in outbound campaign
  messages — `Customer.marketing_opt_in` can only be toggled via the
  `/api/v1/customers/{id}/` API today, not by a customer replying "STOP"
  on WhatsApp. A future phase could wire a reply-keyword check into
  `apps.whatsapp`'s inbound flow.
