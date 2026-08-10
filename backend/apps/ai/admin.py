from django.contrib import admin

from .models import AISettings


@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    list_display = [
        "business",
        "tenant",
        "mode",
        "provider",
        "ai_enabled",
        "human_handoff_enabled",
    ]
    list_filter = ["mode", "provider", "ai_enabled", "tenant"]
    search_fields = ["business__name"]
