"""WhatsAppBusinessAI — Pagination Classes"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "status": "success",
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "count": {"type": "integer"},
                "total_pages": {"type": "integer"},
                "current_page": {"type": "integer"},
                "next": {"type": "string", "nullable": True},
                "previous": {"type": "string", "nullable": True},
                "results": schema,
            },
        }


class LargeResultsPagination(PageNumberPagination):
    """For export-ready / high-volume endpoints (e.g. analytics, campaigns)."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000
