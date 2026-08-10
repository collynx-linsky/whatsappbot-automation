"""WhatsAppBusinessAI — Customers Serializers"""

from django.utils import timezone
from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "tenant",
            "name",
            "phone",
            "email",
            "location",
            "tags",
            "source",
            "status",
            "notes",
            "marketing_opt_in",
            "marketing_opt_in_at",
            "last_interaction_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "marketing_opt_in_at",
            "last_interaction_at",
            "created_at",
            "updated_at",
        ]

    def validate_phone(self, phone):
        """
        The model enforces (tenant, phone) uniqueness at the DB level, but
        `tenant` is server-injected after this validation runs (see
        core.mixins.TenantScopedCreateMixin) — so DRF can't infer this from
        a UniqueTogetherValidator on the declared fields alone. Checking it
        explicitly here turns a raw IntegrityError (500) into a clean 400.
        """
        request = self.context["request"]
        tenant = request.user.tenant
        if tenant is not None:
            qs = Customer.objects.filter(tenant=tenant, phone=phone)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A customer with this phone number already exists."
                )
        return phone

    def _stamp_opt_in(self, validated_data):
        """`marketing_opt_in_at` records *when* consent was given — real
        compliance evidence, not just a boolean. Re-stamped every time the
        flag is (re)set to True; left untouched on any other update."""
        if validated_data.get("marketing_opt_in") is True:
            validated_data["marketing_opt_in_at"] = timezone.now()
        return validated_data

    def create(self, validated_data):
        return super().create(self._stamp_opt_in(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._stamp_opt_in(validated_data))
