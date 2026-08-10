"""WhatsAppBusinessAI — Tenants URLs (/api/v1/tenants/) — super admin"""

from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("", views.TenantListView.as_view(), name="list"),
    path("onboard/", views.OnboardBusinessView.as_view(), name="onboard"),
    path("plans/", views.PlanListCreateView.as_view(), name="plans"),
    path("<uuid:pk>/", views.TenantDetailView.as_view(), name="detail"),
    path("<uuid:pk>/suspend/", views.SuspendTenantView.as_view(), name="suspend"),
    path("<uuid:pk>/activate/", views.ActivateTenantView.as_view(), name="activate"),
]
