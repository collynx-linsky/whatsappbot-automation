"""WhatsAppBusinessAI — Orders URLs (/api/v1/orders/)"""

from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.OrderDetailView.as_view(), name="detail"),
    path("<uuid:pk>/status/", views.OrderStatusTransitionView.as_view(), name="status"),
]
