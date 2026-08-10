"""WhatsAppBusinessAI — Knowledge Base URLs (/api/v1/knowledge/)"""

from django.urls import path

from . import views

app_name = "knowledge"

urlpatterns = [
    path(
        "documents/", views.KnowledgeDocumentListCreateView.as_view(), name="document-list-create"
    ),
    path(
        "documents/<uuid:pk>/", views.KnowledgeDocumentDetailView.as_view(), name="document-detail"
    ),
    path(
        "documents/<uuid:pk>/chunks/",
        views.KnowledgeDocumentChunksView.as_view(),
        name="document-chunks",
    ),
]
