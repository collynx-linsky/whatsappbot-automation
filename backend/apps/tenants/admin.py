from django.contrib import admin

from .models import Plan, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "status", "plan", "created_at"]
    list_filter = ["status", "plan"]
    search_fields = ["name", "slug"]
    readonly_fields = ["id", "slug", "created_at", "updated_at"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "price_monthly",
        "currency",
        "is_active",
        "is_default",
        "sort_order",
    ]
    list_filter = ["is_active", "is_default"]
    search_fields = ["name"]
