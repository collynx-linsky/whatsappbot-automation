from django.contrib import admin

from .models import MessageEvent, WhatsAppAccount


@admin.register(WhatsAppAccount)
class WhatsAppAccountAdmin(admin.ModelAdmin):
    list_display = ["phone_number", "business", "tenant", "status", "connected_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["phone_number", "phone_number_id", "business__name"]
    # access_token is never shown, even in admin — encrypted field only.
    readonly_fields = ["access_token_encrypted", "connected_at", "last_sync_at"]


@admin.register(MessageEvent)
class MessageEventAdmin(admin.ModelAdmin):
    list_display = ["external_event_id", "whatsapp_account", "event_type", "processed_at"]
    list_filter = ["event_type", "tenant"]
    search_fields = ["external_event_id"]

    def has_add_permission(self, request):
        return False
