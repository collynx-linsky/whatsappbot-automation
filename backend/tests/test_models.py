"""Model-level behavior: slugs, soft delete, audit logging."""

import pytest

from apps.common.models import AuditLog
from apps.tenants.models import Tenant


@pytest.mark.django_db
def test_tenant_slug_auto_generated_and_deduplicated():
    t1 = Tenant.objects.create(name="Acme Co")
    t2 = Tenant.objects.create(name="Acme Co")
    assert t1.slug == "acme-co"
    assert t2.slug == "acme-co-2"


@pytest.mark.django_db
def test_user_creation_writes_audit_log(tenant_a):
    _, _, owner_a = tenant_a
    assert AuditLog.objects.filter(action="USER_CREATED", user=owner_a).exists()
