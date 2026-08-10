# Multi-Tenancy

**The rule, stated once:** a tenant id, business id, or user id coming from
the client (a header, a query param, a request body field, a URL path
segment) is never trusted to determine what data a request can touch.
Tenant scope is always derived from the authenticated user's own
server-side state.

## How `request.tenant` gets set

`core.middleware.TenantMiddleware` (runs before every view):

1. Authenticates the request's JWT itself — using the same
   `JWTAuthentication` class DRF uses — because plain Django middleware
   runs *before* DRF resolves `request.user` for API requests. Skipping
   this step would mean checking an `AnonymousUser` and never resolving a
   tenant at all.
2. If the caller is an ordinary user (not a super admin) with a tenant:
   `request.tenant = caller's own tenant`. Full stop — nothing else can
   override this for a regular user.
3. If the caller `is_superuser`: there's no tenant of their own, so an
   `X-Tenant-ID` header is honored *only* for super admins, and only after
   confirming that tenant actually exists. This lets platform-admin tooling
   act on a specific tenant; it is not a privilege a regular user can use,
   because step 2 already locked their tenant to their own before this
   branch is ever reached.

`core.permissions.IsTenantMember` then double-checks
`request.user.tenant_id == request.tenant.id` at the permission layer —
so even if `request.tenant` were somehow wrong, the permission class is a
second independent check, not just the middleware's say-so.

## How views scope querysets

Every tenant-scoped view filters its queryset by
`request.user.tenant_id` directly (see
`apps.businesses.views.TenantScopedQuerysetMixin`) — **not** by trusting an
id parsed out of the URL. Requesting `/api/v1/businesses/<some-other-tenant's-id>/`
returns `404`, not `403` — the existence of another tenant's object is not
leaked by the response code.

Super admins bypass the tenant filter entirely (platform oversight is an
explicit spec requirement), but the 4-role permission classes
(`IsStaffOrAbove`, `IsManagerOrAbove`, `IsBusinessOwner`) all special-case
`is_superuser` so the bypass is consistent between "can they even hit this
endpoint" and "what does the queryset return."

## `core.models.TenantAwareModel` / `BaseModel`

The base model's manager (`TenantAwareManager`) exposes `.for_tenant(tenant)`
but does **not** silently auto-filter every query by some ambient
"current tenant." That pattern (thread-local current-tenant magic) is
convenient but makes it easy to forget you're relying on it, or to leak
data the one time a query runs outside a request context (a management
command, a Celery task). Explicit `.filter(tenant=...)` — or the tenant
being baked into the URL-derived queryset as in `businesses/views.py` — is
slightly more typing and considerably harder to get wrong silently.

## Verified live (not just asserted)

`backend/tests/test_tenant_isolation.py` is the automated version of the
critical spec-section-29 requirement, and was also proven by hand against a
running server this session:

- Business A's owner lists `/api/v1/businesses/` → sees only their own business.
- Business A's owner requests Business B's business by its real UUID → `404`.
- Business A's owner `PATCH`es Business B's business by UUID → `404`, no
  change persisted.
- Business A's owner sends `X-Tenant-ID: <tenant B's id>` → still `404` (the
  header is ignored for non-superusers).
- A super admin sees all businesses across all tenants.
- A non-super-admin hitting the platform-wide `/api/v1/tenants/` list gets `403`.

## What's tenant-scoped vs. platform-wide today

| Model | Scope |
|---|---|
| `Tenant`, `Plan` | Platform-wide (super admin manages) |
| `Business` | Tenant-scoped |
| `User` | Tenant-scoped (except `super_admin`, which has `tenant=None`) |
| `AuditLog` | Tenant-scoped where `tenant` is set; platform actions may have `tenant=None` |

Every domain model added in later phases (customers, conversations,
products, orders, ...) inherits `core.models.BaseModel` and is
tenant-scoped by construction.
