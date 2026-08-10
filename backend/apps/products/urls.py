"""WhatsAppBusinessAI — Products URLs (/api/v1/products/)"""

from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.ProductListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.ProductDetailView.as_view(), name="detail"),
]
