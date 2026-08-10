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

## Not built yet

Every other `/api/v1/<domain>/` path listed in the master spec
(`customers/`, `conversations/`, `messages/`, `whatsapp/`, `ai/`,
`knowledge/`, `products/`, `orders/`, `campaigns/`, `analytics/`,
`notifications/`, `billing/`, `audit/`) is not implemented — see
`docs/ROADMAP.md` for which phase builds each one.
