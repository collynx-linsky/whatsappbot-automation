"""WhatsAppBusinessAI — Campaigns URLs (/api/v1/campaigns/)"""

from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("templates/", views.MessageTemplateListCreateView.as_view(), name="template-list-create"),
    path(
        "templates/<uuid:pk>/", views.MessageTemplateDetailView.as_view(), name="template-detail"
    ),
    path("segments/", views.SegmentListCreateView.as_view(), name="segment-list-create"),
    path("segments/<uuid:pk>/", views.SegmentDetailView.as_view(), name="segment-detail"),
    path(
        "segments/<uuid:pk>/preview/", views.SegmentPreviewView.as_view(), name="segment-preview"
    ),
    path("", views.CampaignListCreateView.as_view(), name="campaign-list-create"),
    path("<uuid:pk>/", views.CampaignDetailView.as_view(), name="campaign-detail"),
    path("<uuid:pk>/send/", views.CampaignSendView.as_view(), name="campaign-send"),
    path(
        "<uuid:pk>/recipients/",
        views.CampaignRecipientsView.as_view(),
        name="campaign-recipients",
    ),
]
