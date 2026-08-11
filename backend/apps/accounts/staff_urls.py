"""
WhatsAppBusinessAI — Staff Management URLs (/api/v1/staff/)

Separate from accounts/urls.py (mounted at /api/v1/auth/) — staff is its
own resource collection, not an auth concern, even though the model lives
in apps.accounts.
"""

from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.StaffListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.StaffDetailView.as_view(), name="detail"),
    path("<uuid:pk>/mfa-reset/", views.MFAResetView.as_view(), name="mfa-reset"),
]
