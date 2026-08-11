"""
`python manage.py audit_permissions`

Priorities 1+2 of this security-hardening pass ("multi-tenant isolation"
and "RBAC + permission engine") asked for an audit, not a rewrite — this
codebase's tenant-scoping (core.mixins.TenantScopedQuerysetMixin) and RBAC
(core.permissions) were already extensively built and tested phase by
phase. This command makes that audit a real, re-runnable check instead of
a one-off manual review that goes stale the moment a new view is added,
by walking every registered URL and checking two things automatically:

1. Every DRF view either sets `permission_classes` or overrides
   `get_permissions()` — i.e. nothing silently relies on the bare
   platform-default `IsAuthenticated` (which would let ANY authenticated
   user of ANY role/tenant through, regardless of what the endpoint
   actually does).
2. Every view with a `queryset`/`get_queryset` either uses
   `core.mixins.TenantScopedQuerysetMixin` or defines its own
   `get_queryset()` (flagged for manual review — the command can't prove
   a hand-rolled `get_queryset()` actually filters by tenant, only that
   one exists; see docs/multi-tenancy.md for the reviewed list).

Exits non-zero if it finds a view with neither an explicit permission
setup nor a queryset override at all — safe to wire into CI later
(Priority 10) as a regression guard against a future view accidentally
shipping unguarded.
"""

from django.core.management.base import BaseCommand
from django.urls import get_resolver
from rest_framework import generics
from rest_framework.views import APIView

from core.mixins import TenantScopedQuerysetMixin

# Views that legitimately have no tenant scoping — platform-wide by
# design, not an oversight. Checked by name since they live in several
# apps; keep this list in sync with docs/multi-tenancy.md's own list.
KNOWN_PLATFORM_WIDE_VIEWS = {
    "TenantListView",  # Tenant IS the isolation boundary — nothing to scope it by
    "TenantDetailView",
    "PlanListCreateView",  # shared plan catalog, not tenant data
    "PublicPlanListView",  # same shared catalog, filtered to active plans, AllowAny
}

# Views with a hand-rolled get_queryset() already manually reviewed and
# confirmed to filter by tenant (with a correct superuser bypass) — see
# docs/multi-tenancy.md's audit section. Flagged here so a *future*
# hand-rolled get_queryset() that ISN'T on this list stands out instead
# of blending in.
REVIEWED_MANUAL_TENANT_SCOPING = {
    "StaffListCreateView",
    "StaffDetailView",
    "ConversationAssignmentHistoryView",
    "KnowledgeDocumentChunksView",
    "CampaignRecipientsView",
}


def _walk(patterns, prefix=""):
    results = []
    for p in patterns:
        if hasattr(p, "url_patterns"):
            results += _walk(p.url_patterns, prefix + str(p.pattern))
        else:
            results.append((prefix + str(p.pattern), p))
    return results


class Command(BaseCommand):
    help = (
        "Audit every registered view for explicit permission checks and tenant-scoped querysets."
    )

    def handle(self, *args, **options):
        all_patterns = _walk(get_resolver().url_patterns)

        seen = set()
        unguarded_permissions = []
        unreviewed_manual_scoping = []

        for path, p in all_patterns:
            callback = getattr(p, "callback", None)
            view_class = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
            if view_class is None or view_class.__name__ in seen:
                continue
            seen.add(view_class.__name__)

            if issubclass(view_class, APIView):
                has_explicit_perm = "permission_classes" in view_class.__dict__
                has_get_permissions = "get_permissions" in view_class.__dict__
                # permission_classes=() (SimpleJWT's own TokenViewBase) is a
                # deliberate, explicit "no permission check" — not a gap.
                inherited_empty = view_class.permission_classes == ()
                if not (has_explicit_perm or has_get_permissions or inherited_empty):
                    unguarded_permissions.append((path, view_class))

            if issubclass(view_class, generics.GenericAPIView):
                has_queryset = (
                    "queryset" in view_class.__dict__ or "get_queryset" in view_class.__dict__
                )
                if not has_queryset:
                    continue
                if issubclass(view_class, TenantScopedQuerysetMixin):
                    continue
                if view_class.__name__ in KNOWN_PLATFORM_WIDE_VIEWS:
                    continue
                if view_class.__name__ not in REVIEWED_MANUAL_TENANT_SCOPING:
                    unreviewed_manual_scoping.append((path, view_class))

        self.stdout.write(
            f"Checked {len(seen)} distinct view classes across {len(all_patterns)} URL patterns.\n"
        )

        if unguarded_permissions:
            self.stdout.write(self.style.ERROR("Views with NO permission check at all:"))
            for path, vc in unguarded_permissions:
                self.stdout.write(f"  {path}  ->  {vc.__module__}.{vc.__name__}")
        else:
            self.stdout.write(
                self.style.SUCCESS("[OK] Every view has an explicit permission check.")
            )

        if unreviewed_manual_scoping:
            self.stdout.write(
                self.style.WARNING(
                    "\nViews with a hand-rolled get_queryset() not yet on the reviewed list "
                    "(may be fine — but confirm it filters by tenant, then add it to "
                    "REVIEWED_MANUAL_TENANT_SCOPING in this command):"
                )
            )
            for path, vc in unreviewed_manual_scoping:
                self.stdout.write(f"  {path}  ->  {vc.__module__}.{vc.__name__}")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "[OK] Every queryset-based view uses TenantScopedQuerysetMixin, is a "
                    "known platform-wide view, or is on the reviewed manual-scoping list."
                )
            )

        if unguarded_permissions:
            raise SystemExit(1)
