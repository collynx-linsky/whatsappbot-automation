"""WhatsAppBusinessAI — Tenants Serializers"""

from rest_framework import serializers

from apps.businesses.models import Business

from .models import Plan, Tenant


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price_monthly",
            "currency",
            "max_users",
            "max_whatsapp_accounts",
            "max_ai_messages_per_month",
            "max_customers",
            "max_campaigns_per_month",
            "max_storage_mb",
            "is_active",
            "is_default",
            "sort_order",
        ]
        read_only_fields = ["id"]


class PublicPlanSerializer(serializers.ModelSerializer):
    """
    The subset of Plan fields safe to show an anonymous visitor on the
    public marketing/pricing page — no `is_active`/`is_default` (internal
    bookkeeping, not a customer's concern) and no `max_storage_mb` (not
    actually enforced anywhere yet — see docs/billing.md — so advertising
    it as a real limit would overpromise what this platform currently
    does).
    """

    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price_monthly",
            "currency",
            "max_users",
            "max_whatsapp_accounts",
            "max_ai_messages_per_month",
            "max_customers",
            "max_campaigns_per_month",
            "sort_order",
        ]
        read_only_fields = fields


class TenantSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    business_count = serializers.IntegerField(source="businesses.count", read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "plan",
            "plan_name",
            "business_count",
            "trial_ends_at",
            "subscription_ends_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class OnboardBusinessSerializer(serializers.Serializer):
    """
    Super-admin-only: creates a Tenant + Business + BUSINESS_OWNER user in
    one atomic call — the platform's "create a business" onboarding step
    (spec sections 6, 40). A temporary password is generated server-side and
    returned once in the response (and emailed via EMAIL_BACKEND) — it is
    never accepted as client input.
    """

    tenant_name = serializers.CharField(max_length=255)
    plan_id = serializers.UUIDField(required=False, allow_null=True)

    business_name = serializers.CharField(max_length=255)
    business_category = serializers.ChoiceField(
        choices=Business.Category.choices, default=Business.Category.OTHER
    )
    business_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    business_email = serializers.EmailField(required=False, allow_blank=True)
    business_country = serializers.CharField(max_length=100, default="Kenya")
    business_currency = serializers.CharField(max_length=3, default="KES")

    owner_email = serializers.EmailField()
    owner_first_name = serializers.CharField(max_length=100)
    owner_last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_owner_email(self, value):
        from apps.accounts.models import User

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
