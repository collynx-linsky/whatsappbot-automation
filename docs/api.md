# API Reference

Base URL: `http://localhost:8000/api/v1/`
Interactive docs (drf-spectacular): `/api/docs/` (Swagger), `/api/redoc/`,
raw schema at `/api/schema/`.

## Response envelope

Every error response has the same shape
(`core.exceptions.custom_exception_handler`):

```json
{
  "status": "error",
  "message": "Human-readable summary",
  "errors": { "field_name": ["..."], "non_field_errors": ["..."] },
  "code": "machine_readable_code"
}
```

List endpoints are paginated (`core.pagination.StandardResultsPagination`,
25/page by default, `?page=`/`?page_size=`):

```json
{
  "status": "success",
  "count": 3,
  "total_pages": 1,
  "current_page": 1,
  "next": null,
  "previous": null,
  "results": [ ... ]
}
```

## Auth — `/api/v1/auth/`

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `login/` | none | `{email, password}` → `{access, refresh, user}`. Locks account after 5 failures. |
| POST | `refresh/` | none | `{refresh}` → `{access}` (simplejwt default view). |
| POST | `logout/` | required | `{refresh}` → blacklists it. |
| GET | `me/` | required | Current user's own profile. |
| POST | `forgot-password/` | none | `{email}` → always 200; emails a reset link (console backend in dev). |
| POST | `reset-password/` | none | `{token, new_password}`. |

## Staff — `/api/v1/staff/`

Team roster for the caller's own tenant. Separate from `/auth/` — this is
user *management*, not login. See `docs/database.md` for the role rules
enforced.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `` | staff+ | Team roster (owner + manager + staff) for the caller's own tenant. |
| POST | `` | business owner | `{email, first_name, last_name?, phone?, role}` — `role` must be `manager` or `staff` (never `business_owner`/`super_admin`). Generates a temporary password, emails it, returns it once. |
| GET | `<uuid:pk>/` | staff+ | 404 if in another tenant. |
| PATCH | `<uuid:pk>/` | business owner | Edit role/`is_active`/profile fields. Cannot target the business owner or the caller's own account (400) — self-service role changes and self-lockout aren't possible via this endpoint. |

## Tenants — `/api/v1/tenants/` (super admin only, except `plans/` GET)

| Method | Path | Notes |
|---|---|---|
| GET | `` | List all tenants. Filter: `?status=`, `?plan=`. Search: `?search=`. |
| GET | `<uuid:pk>/` | Retrieve one tenant. |
| POST | `onboard/` | Atomically creates Tenant + Business + BUSINESS_OWNER user. Returns `temporary_password` once. |
| POST | `<uuid:pk>/suspend/` | Sets `status=suspended`. |
| POST | `<uuid:pk>/activate/` | Sets `status=active`. |
| GET | `plans/` | List plans (any authenticated user — for pricing display). |
| POST | `plans/` | Create a plan (super admin only). |

`onboard/` payload:
```json
{
  "tenant_name": "ABC Electronics Ltd",
  "plan_id": "uuid (optional — falls back to the default plan)",
  "business_name": "ABC Electronics",
  "business_category": "electronics",
  "business_phone": "", "business_email": "",
  "business_country": "Kenya", "business_currency": "KES",
  "owner_email": "owner@abcelectronics.test",
  "owner_first_name": "Amina", "owner_last_name": "Juma"
}
```

## Businesses — `/api/v1/businesses/`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `` | staff+ | Businesses in the caller's own tenant (super admin sees all). |
| GET | `<uuid:pk>/` | staff+ | 404 if it belongs to another tenant. |
| PATCH | `<uuid:pk>/` | manager+ | 404 if it belongs to another tenant. |

## Customers — `/api/v1/customers/` (staff+)

| Method | Path | Notes |
|---|---|---|
| GET | `` | List customers in the caller's own tenant. Filter: `?status=`, `?source=`. Search: `?search=` (name/phone/email). |
| POST | `` | Create a customer. `tenant` is always server-injected. `(tenant, phone)` must be unique — a duplicate returns a clean 400, not a 500. |
| GET | `<uuid:pk>/` | 404 if it belongs to another tenant. |
| PATCH | `<uuid:pk>/` | 404 if it belongs to another tenant. |

## Conversations — `/api/v1/conversations/` (staff+)

| Method | Path | Notes |
|---|---|---|
| GET | `` | List conversations in the caller's own tenant. Filter: `?status=`, `?assigned_to=`, `?ai_enabled=`. Search: `?search=` (customer name/phone). |
| POST | `` | `{"customer": "<uuid>"}` opens a conversation. The customer must belong to the caller's own tenant — passing a real id from another tenant returns 400, not a leak. |
| GET / PATCH | `<uuid:pk>/` | 404 if it belongs to another tenant. |
| POST | `<uuid:pk>/assign/` | `{"user_id": "<uuid>" \| null}` — assigns/unassigns staff and logs a `ConversationAssignment` entry. The user must belong to the caller's own tenant. |
| GET | `<uuid:pk>/assignments/` | Assignment history for one conversation. |

## Messages — `/api/v1/messages/` (staff+)

| Method | Path | Notes |
|---|---|---|
| GET | `` | List messages. Filter: `?conversation=<uuid>` (typical usage), `?sender_type=`, `?direction=`. |
| POST | `` | `{"conversation": "<uuid>", "sender_type": "staff", "content": "..."}`. Only `sender_type=staff` is accepted this phase — customer/AI messages arrive via the not-yet-built WhatsApp webhook / AI engine. `direction`, `sender_user`, and `status` are always server-derived. Posting updates the parent conversation's `last_message_preview`/`last_message_at`/`unread_count` automatically. |
| GET | `<uuid:pk>/` | 404 if it belongs to another tenant. |

## WhatsApp — `/api/v1/whatsapp/`

See `docs/whatsapp.md` for the full inbound/outbound flow and security model.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `accounts/` | manager+ | List WhatsApp accounts in the caller's own tenant. `access_token` is never included in the response. |
| POST | `accounts/` | manager+ | Connect a number: `{business, phone_number, phone_number_id, business_account_id, access_token}`. `business` must belong to the caller's own tenant. |
| GET / PATCH | `accounts/<uuid:pk>/` | manager+ | 404 if it belongs to another tenant. |
| GET | `webhook/` | none (Meta) | Subscription verification handshake — `?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`. |
| POST | `webhook/` | none (Meta) | Inbound message/status events. Requires a valid `X-Hub-Signature-256` header (HMAC-SHA256 of the raw body, `WHATSAPP_APP_SECRET`) — unsigned or wrongly-signed requests get `403`. Idempotent per WhatsApp message id. |

## Products — `/api/v1/products/`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `` | staff+ | Catalog for the caller's own tenant. Filter: `?status=`, `?category=`, `?is_available=`. Search: `?search=` (name/sku/description). |
| POST | `` | manager+ | `{name, sku?, description?, category?, price, currency?, stock?}`. |
| GET | `<uuid:pk>/` | staff+ | 404 if in another tenant. |
| PATCH | `<uuid:pk>/` | manager+ | 404 if in another tenant. |

## Orders — `/api/v1/orders/`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `` | staff+ | Orders in the caller's own tenant. Filter: `?status=`, `?customer=`. |
| POST | `` | staff+ | `{customer, conversation?, notes?, items: [{product, quantity}]}` — always created as `pending`; `total_amount` and each item's `unit_price`/`product_name` are computed/snapshotted server-side, never client input. Both `customer` and every `items[].product` must belong to the caller's own tenant. |
| GET | `<uuid:pk>/` | staff+ | 404 if in another tenant. Includes nested `items`. |
| PATCH | `<uuid:pk>/` | staff+ | Only `notes` is writable here — `status` is read-only on this endpoint. |
| POST | `<uuid:pk>/status/` | staff+ | `{"status": "confirmed"}` — the only way to change an order's status. Validated against `Order.ALLOWED_TRANSITIONS` (see `docs/database.md`); an invalid transition (skipping a stage, moving backwards, or touching a terminal order) returns `400`. Moving to `confirmed` stamps `confirmed_by`/`confirmed_at`. |

`POST /orders/` payload:
```json
{
  "customer": "<uuid>",
  "conversation": "<uuid> (optional)",
  "notes": "",
  "items": [{"product": "<uuid>", "quantity": 2}]
}
```

## AI — `/api/v1/ai/`

See `docs/ai.md` for the full reply/handoff flow. Singleton-per-tenant —
no `<uuid:pk>` in either URL, unlike every other resource in this API.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `settings/` | manager+ | The caller's own business's AI config. Created lazily with model defaults on first request if it doesn't exist yet. |
| PATCH | `settings/` | manager+ | Partial update — any subset of `AISettings`' writable fields (see `docs/database.md`). |
| POST | `test/` | manager+ | Onboarding "test your AI" step. `{"message": "..."}` → runs the same handoff-check + prompt-building logic as a real inbound message, without touching `Conversation`/`Message`. Returns `{handed_off, reason?, reply?, confidence?}`. |

## Not built yet

Every other `/api/v1/<domain>/` path listed in the master spec
(`knowledge/`, `campaigns/`, `analytics/`, `notifications/`,
`billing/`, `audit/`) is not implemented — see `docs/ROADMAP.md` for which
phase builds each one.
