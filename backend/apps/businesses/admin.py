from django.contrib import admin

from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "tenant", "category", "country", "is_active", "created_at"]
    list_filter = ["category", "is_active", "country"]
    search_fields = ["name", "legal_name", "tenant__name"]
