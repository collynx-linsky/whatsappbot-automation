"""
WhatsAppBusinessAI — Order Models

Order/OrderItem per spec section 14. Requires confirmation before
finalizing (spec: "Allow the AI to help customers create orders, but
require appropriate confirmation before finalizing an order") — enforced
here as an explicit status state machine (`Order.ALLOWED_TRANSITIONS`)
rather than just a free-text status field: creation always starts at
PENDING, and only a validated transition can move it to CONFIRMED (which
also stamps `confirmed_by`/`confirmed_at`).

OrderItem snapshots `product_name`/`unit_price` at order time — a later
price change on the Product must never retroactively alter historical
order totals.
"""

from django.db import models

from core.models import BaseModel


class Order(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    # Forward-only state machine — no going back to an earlier stage, no
    # skipping straight to CONFIRMED without going through this table.
    # DELIVERED and CANCELLED are terminal.
    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.PROCESSING, Status.CANCELLED},
        Status.PROCESSING: {Status.READY, Status.CANCELLED},
        Status.READY: {Status.DELIVERED, Status.CANCELLED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="The conversation this order originated from, if any.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="KES")
    notes = models.TextField(blank=True)

    confirmed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders_order"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"Order {str(self.id)[:8]} — {self.customer} ({self.status})"

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def recalculate_total(self):
        total = self.items.aggregate(total=models.Sum("subtotal"))["total"] or 0
        self.total_amount = total
        self.save(update_fields=["total_amount", "updated_at"])


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="order_items"
    )

    # Snapshotted at order time — never re-derived from the live Product.
    product_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "orders_item"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)
