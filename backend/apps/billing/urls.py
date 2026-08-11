"""WhatsAppBusinessAI — Billing URLs (/api/v1/billing/)"""

from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("usage/", views.UsageSummaryView.as_view(), name="usage"),
    path("invoices/", views.InvoiceListView.as_view(), name="invoice-list"),
    path("invoices/<uuid:pk>/", views.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("invoices/generate/", views.GenerateInvoiceView.as_view(), name="invoice-generate"),
]
