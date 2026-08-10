"""WhatsAppBusinessAI — Root URL Configuration"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

api_v1_patterns = [
    path("auth/", include("apps.accounts.urls")),
    path("staff/", include("apps.accounts.staff_urls")),
    path("tenants/", include("apps.tenants.urls")),
    path("businesses/", include("apps.businesses.urls")),
    path("customers/", include("apps.customers.urls")),
    path("conversations/", include("apps.conversations.urls")),
    path("messages/", include("apps.messages.urls")),
    path("whatsapp/", include("apps.whatsapp.urls")),
    path("products/", include("apps.products.urls")),
    path("orders/", include("apps.orders.urls")),
    path("ai/", include("apps.ai.urls")),
]


def api_root(request):
    """
    This is a backend API only — there's no server-rendered homepage here
    (the Next.js frontend at :3000 is the actual UI). Hitting `/` bare
    otherwise 404s with Django's raw debug page, which is confusing when
    you're just checking the server is up — so return a small pointer
    instead.
    """
    return JsonResponse(
        {
            "platform": settings.PLATFORM_NAME,
            "status": "ok",
            "api": request.build_absolute_uri("/api/v1/"),
            "docs": request.build_absolute_uri("/api/docs/"),
            "admin": request.build_absolute_uri("/admin/"),
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
