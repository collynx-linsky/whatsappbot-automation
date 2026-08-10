from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "sku",
        "tenant",
        "price",
        "currency",
        "stock",
        "status",
        "is_available",
    ]
    list_filter = ["status", "is_available", "tenant"]
    search_fields = ["name", "sku"]
