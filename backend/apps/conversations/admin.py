from django.contrib import admin

from .models import Conversation, ConversationAssignment


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["customer", "tenant", "status", "assigned_to", "ai_enabled", "last_message_at"]
    list_filter = ["status", "channel", "ai_enabled", "tenant"]
    search_fields = ["customer__name", "customer__phone"]


@admin.register(ConversationAssignment)
class ConversationAssignmentAdmin(admin.ModelAdmin):
    list_display = ["conversation", "user", "assigned_by", "assigned_at", "unassigned_at"]
    list_filter = ["tenant"]
