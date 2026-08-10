from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "tenant", "status", "source", "last_interaction_at"]
    list_filter = ["status", "source", "tenant"]
    search_fields = ["name", "phone", "email"]
