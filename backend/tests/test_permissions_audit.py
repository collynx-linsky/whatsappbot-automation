"""
Priorities 1+2 (multi-tenant isolation, RBAC): a real regression guard,
not just a one-off manual review. Runs `manage.py audit_permissions`
against the live URL configuration on every test run — if a future view
ships with no permission check at all, this fails immediately instead of
silently shipping an unguarded endpoint.
"""

import pytest
from django.core.management import call_command


class TestPermissionsAudit:
    def test_every_view_has_an_explicit_permission_check(self, capsys):
        # call_command raises SystemExit(1) via the command itself if it
        # finds an unguarded view — a clean call (no exception) IS the
        # assertion here.
        call_command("audit_permissions")
        output = capsys.readouterr().out
        assert "[OK] Every view has an explicit permission check." in output

    def test_flags_a_genuinely_unguarded_view(self):
        """Proves the audit isn't a no-op — it actually detects the failure case."""
        from django.urls import URLPattern, get_resolver
        from rest_framework.views import APIView

        class _DeliberatelyUnguardedView(APIView):
            def get(self, request):
                return None

        resolver = get_resolver()
        fake_pattern = URLPattern("audit-test-unguarded/", _DeliberatelyUnguardedView.as_view())
        resolver.url_patterns.append(fake_pattern)
        try:
            with pytest.raises(SystemExit):
                call_command("audit_permissions")
        finally:
            resolver.url_patterns.remove(fake_pattern)
