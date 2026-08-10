"""
WhatsAppBusinessAI — Product Model

Fields per spec section 13. `image` is a single ImageField (matching the
established `Business.logo` pattern) rather than a gallery — no multi-image
upload infrastructure exists yet; see docs/ROADMAP.md.
"""

from django.db import models

from core.models import BaseModel


class Product(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=255)
    sku = models.CharField(
        max_length=100, blank=True, help_text="Optional — not every business tracks SKUs."
    )
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)

    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")

    stock = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(
        default=True, help_text="Manual override — can be marked unavailable even with stock > 0."
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    image = models.ImageField(upload_to="products/images/", null=True, blank=True)

    class Meta:
        db_table = "products_product"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "category"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "sku"],
                condition=~models.Q(sku=""),
                name="unique_product_sku_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.currency} {self.price})"

    @property
    def is_orderable(self) -> bool:
        return self.is_available and self.status == self.Status.ACTIVE and self.stock > 0
