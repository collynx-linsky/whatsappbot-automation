from django.contrib import admin

from .models import Invoice, UsageRecord


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ["tenant", "metric", "period", "count"]
    list_filter = ["metric", "period"]

    def has_add_permission(self, request):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "tenant", "period_start", "amount", "currency", "status"]
    list_filter = ["status", "currency"]
    search_fields = ["invoice_number", "tenant__name"]
    readonly_fields = ["invoice_number"]
