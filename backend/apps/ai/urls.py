"""WhatsAppBusinessAI — AI URLs (/api/v1/ai/)"""

from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("settings/", views.AISettingsView.as_view(), name="settings"),
    path("test/", views.AITestView.as_view(), name="test"),
]
