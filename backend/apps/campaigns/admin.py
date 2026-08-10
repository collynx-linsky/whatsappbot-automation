from django.contrib import admin

from .models import Campaign, CampaignRecipient, MessageTemplate, Segment


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "tenant", "category", "status", "language_code"]
    list_filter = ["status", "category", "tenant"]
    search_fields = ["name", "whatsapp_template_name", "business__name"]


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "tenant"]
    list_filter = ["tenant"]
    search_fields = ["name", "business__name"]


class CampaignRecipientInline(admin.TabularInline):
    model = CampaignRecipient
    extra = 0
    fields = ["customer", "status", "skip_reason", "sent_at"]
    readonly_fields = ["customer", "status", "skip_reason", "sent_at"]
    can_delete = False


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "business",
        "tenant",
        "status",
        "recipient_count",
        "sent_count",
        "failed_count",
        "skipped_count",
    ]
    list_filter = ["status", "tenant"]
    search_fields = ["name", "business__name"]
    readonly_fields = [
        "recipient_count",
        "sent_count",
        "failed_count",
        "skipped_count",
        "started_at",
        "completed_at",
        "error_message",
    ]
    inlines = [CampaignRecipientInline]
