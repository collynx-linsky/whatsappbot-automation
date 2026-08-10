"""WhatsAppBusinessAI — WhatsApp URLs (/api/v1/whatsapp/)"""

from django.urls import path

from . import views

app_name = "whatsapp"

urlpatterns = [
    path("accounts/", views.WhatsAppAccountListCreateView.as_view(), name="account-list-create"),
    path("accounts/<uuid:pk>/", views.WhatsAppAccountDetailView.as_view(), name="account-detail"),
    path("webhook/", views.WhatsAppWebhookView.as_view(), name="webhook"),
]
