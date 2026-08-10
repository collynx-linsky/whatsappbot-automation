# Architecture

## Overview

WABA AI is a multi-tenant SaaS platform: one platform administrator (Super
Admin) manages many independent businesses, each with its own WhatsApp
number, AI assistant, customers, and data — fully isolated from every other
business.

```
                         INTERNET
                            |
                     Next.js frontend  <-- browser (JWT in localStorage)
                            |
                     Django REST API  (/api/v1/...)
                       /         \
              PostgreSQL         Redis
           (tenant-scoped data)  (cache / Celery broker, later phases)
```

## Layering

- **`core/`** — shared, app-agnostic building blocks every domain app
  depends on: abstract base models (`TimeStampedModel`, `SoftDeleteModel`,
  `TenantAwareModel`, `BaseModel`), the tenant-resolution middleware, DRF
  permission classes, the exception handler / response envelope, and
  pagination. Nothing here knows about "businesses" or "WhatsApp" —
  it's the platform's foundation layer.
- **`apps/<domain>/`** — one Django app per business capability
  (`tenants`, `businesses`, `accounts`, and later `whatsapp`,
  `conversations`, `products`, ...). Each app owns its own
  `models.py` / `serializers.py` / `views.py` / `urls.py`.
- **Views stay thin.** Validation lives in serializers; anything beyond a
  single-model create/update (the onboarding flow that creates a Tenant +
  Business + User atomically, for example) lives directly in the view for
  now as a `transaction.atomic` block. As domain logic grows in later
  phases, extract a `services.py` per app rather than letting views bloat —
  see `docs/development.md` for the convention once it's needed.

## Request lifecycle (a tenant-scoped API call)

```
Request
  -> CorsMiddleware / SecurityMiddleware (Django)
  -> core.middleware.TenantMiddleware
       - authenticates the JWT itself (same JWTAuthentication class DRF
         uses) because Django middleware runs *before* DRF resolves
         request.user for API requests
       - sets request.tenant = the caller's own tenant (never a
         client-supplied id) — see docs/multi-tenancy.md
  -> core.middleware.RequestLoggingMiddleware (structured logging)
  -> DRF view
       - re-authenticates via JWTAuthentication (DRF's own auth flow)
       - permission_classes (core.permissions) check role + tenant match
       - queryset scoped to request.user.tenant_id
  -> core.exceptions.custom_exception_handler on any error
       -> {"status": "error", "message", "errors", "code"} envelope
  -> Response
```

## AI & Messaging provider abstraction (built later, designed now)

The spec requires the AI layer and the WhatsApp integration to be
provider-agnostic from day one. This phase doesn't implement either yet
(that's Phases 7–8), but the settings layer already reads
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEFAULT_AI_PROVIDER` and
`WHATSAPP_*` from `.env` so the interface contract is fixed:

```
MessagingProvider (interface)
 |- WhatsAppProvider   (Phase 7)
 |- TelegramProvider   (future)
 \- SMSProvider        (future)

AIProvider (interface)
 |- OpenAIProvider     (Phase 8)
 |- AnthropicProvider  (Phase 8)
 \- FutureProvider
```

## Frontend

Next.js 16 (App Router, Turbopack, TypeScript, Tailwind CSS v4). No
server-side session — the JWT access/refresh pair and the current user are
stored in `localStorage` (`frontend/lib/auth.ts`), and `frontend/lib/api.ts`
is a thin typed fetch wrapper that retries once on 401 after a silent
refresh. Route guarding is a client-side effect (`frontend/lib/useAuth.ts`)
rather than Next.js middleware/proxy, because there's no server-visible
session to inspect — see `docs/development.md` for why.

## What's built vs. deferred

See `docs/ROADMAP.md` for the full phase-by-phase breakdown. This session
(Phase "Foundation + Multi-tenancy + Auth/RBAC") built: project scaffolding,
`Tenant` / `Plan` / `Business` / `User` / `AuditLog` models, JWT
auth + password reset, the 4-role RBAC permission layer, and the super-admin
onboarding flow. Everything under `backend/apps/{whatsapp,conversations,
messages,ai,knowledge,products,orders,campaigns,analytics,notifications,
billing,audit}/` is a placeholder package (just `__init__.py`) — not wired
into `INSTALLED_APPS`, no models — reserved for the phases that build them.
