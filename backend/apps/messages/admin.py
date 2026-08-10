from django.contrib import admin

from .models import Message, MessageAttachment


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "conversation",
        "sender_type",
        "direction",
        "message_type",
        "status",
        "created_at",
    ]
    list_filter = ["sender_type", "direction", "message_type", "status", "tenant"]
    search_fields = ["content"]


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ["message", "file_name", "file_type", "file_size"]
