"""WhatsAppBusinessAI — Customers URLs (/api/v1/customers/)"""

from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.CustomerListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.CustomerDetailView.as_view(), name="detail"),
]
