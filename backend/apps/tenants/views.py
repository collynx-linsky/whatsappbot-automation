"""WhatsAppBusinessAI — Tenants Views (Super Admin)"""

import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.businesses.models import Business
from apps.common.models import AuditLog
from core.permissions import IsSuperAdmin

from .models import Plan, Tenant
from .serializers import OnboardBusinessSerializer, PlanSerializer, TenantSerializer


class TenantListView(generics.ListAPIView):
    """GET /api/v1/tenants/ — all tenants on the platform (super admin only)."""

    permission_classes = [IsSuperAdmin]
    serializer_class = TenantSerializer
    queryset = Tenant.objects.select_related("plan").all()
    filterset_fields = ["status", "plan"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]


class TenantDetailView(generics.RetrieveAPIView):
    """GET /api/v1/tenants/{id}/ (super admin only)."""

    permission_classes = [IsSuperAdmin]
    serializer_class = TenantSerializer
    queryset = Tenant.objects.select_related("plan").all()


class OnboardBusinessView(APIView):
    """
    POST /api/v1/tenants/onboard/ (super admin only)

    Creates a Tenant + Business + BUSINESS_OWNER user atomically. Returns
    the generated temporary password once — the owner must change it after
    first login (enforced client-side in this phase; forced-change flag is
    a Phase-3+ refinement).
    """

    permission_classes = [IsSuperAdmin]

    @transaction.atomic
    def post(self, request):
        serializer = OnboardBusinessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        plan = None
        if data.get("plan_id"):
            plan = Plan.objects.filter(id=data["plan_id"]).first()
        if plan is None:
            plan = Plan.objects.filter(is_default=True, is_active=True).first()

        tenant = Tenant.objects.create(name=data["tenant_name"], plan=plan)

        business = Business.objects.create(
            tenant=tenant,
            name=data["business_name"],
            category=data["business_category"],
            phone=data.get("business_phone", ""),
            email=data.get("business_email", ""),
            country=data["business_country"],
            currency=data["business_currency"],
        )

        temporary_password = secrets.token_urlsafe(12)
        owner = User.objects.create_user(
            email=data["owner_email"],
            password=temporary_password,
            first_name=data["owner_first_name"],
            last_name=data.get("owner_last_name", ""),
            role=User.Role.BUSINESS_OWNER,
            tenant=tenant,
        )

        AuditLog.log(
            action="BUSINESS_ONBOARDED",
            user=request.user,
            tenant=tenant,
            obj=business,
            metadata={"owner_email": owner.email},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        send_mail(
            subject=f"Welcome to {settings.PLATFORM_NAME}",
            message=(
                f"An account has been created for {business.name} on {settings.PLATFORM_NAME}.\n\n"
                f"Login: {owner.email}\n"
                f"Temporary password: {temporary_password}\n\n"
                f"Sign in at {settings.FRONTEND_URL}/login and change your password."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            fail_silently=True,
        )

        return Response(
            {
                "tenant": TenantSerializer(tenant).data,
                "owner": UserSerializer(owner).data,
                "temporary_password": temporary_password,
            },
            status=status.HTTP_201_CREATED,
        )


class SuspendTenantView(APIView):
    """POST /api/v1/tenants/{id}/suspend/ (super admin only)."""

    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        tenant = generics.get_object_or_404(Tenant, pk=pk)
        tenant.status = Tenant.Status.SUSPENDED
        tenant.save(update_fields=["status", "updated_at"])
        AuditLog.log(action="TENANT_SUSPENDED", user=request.user, tenant=tenant, obj=tenant)
        return Response(TenantSerializer(tenant).data)


class ActivateTenantView(APIView):
    """POST /api/v1/tenants/{id}/activate/ (super admin only)."""

    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        tenant = generics.get_object_or_404(Tenant, pk=pk)
        tenant.status = Tenant.Status.ACTIVE
        tenant.save(update_fields=["status", "updated_at"])
        AuditLog.log(action="TENANT_ACTIVATED", user=request.user, tenant=tenant, obj=tenant)
        return Response(TenantSerializer(tenant).data)


class PlanListCreateView(generics.ListCreateAPIView):
    """GET (any authenticated — for pricing/plan selection), POST (super admin only)."""

    serializer_class = PlanSerializer
    queryset = Plan.objects.all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSuperAdmin()]
        return super().get_permissions()
