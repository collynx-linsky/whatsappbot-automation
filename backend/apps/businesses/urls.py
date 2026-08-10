"""WhatsAppBusinessAI — Businesses URLs (/api/v1/businesses/)"""

from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path("", views.BusinessListView.as_view(), name="list"),
    path("<uuid:pk>/", views.BusinessDetailView.as_view(), name="detail"),
]
