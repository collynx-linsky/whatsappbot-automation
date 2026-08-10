"""WhatsAppBusinessAI — Conversations URLs (/api/v1/conversations/)"""

from django.urls import path

from . import views

app_name = "conversations"

urlpatterns = [
    path("", views.ConversationListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.ConversationDetailView.as_view(), name="detail"),
    path("<uuid:pk>/assign/", views.AssignConversationView.as_view(), name="assign"),
    path(
        "<uuid:pk>/assignments/",
        views.ConversationAssignmentHistoryView.as_view(),
        name="assignments",
    ),
]
