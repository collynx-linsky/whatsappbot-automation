"""WhatsAppBusinessAI — Messages URLs (/api/v1/messages/)"""

from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.MessageListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.MessageDetailView.as_view(), name="detail"),
]
