from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "unit_price", "subtotal"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "tenant", "status", "total_amount", "currency", "created_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["customer__name", "customer__phone"]
    inlines = [OrderItemInline]
