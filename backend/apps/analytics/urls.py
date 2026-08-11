"""WhatsAppBusinessAI — Analytics URLs (/api/v1/analytics/)"""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("dashboard/", views.AnalyticsDashboardView.as_view(), name="dashboard"),
    path("platform/", views.PlatformAnalyticsView.as_view(), name="platform"),
]
