import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class GiftCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="gifts/categories/", blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "Gift categories"

    def __str__(self):
        return self.name


class GiftProduct(models.Model):
    category = models.ForeignKey(
        GiftCategory,
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="gifts/products/", blank=True, null=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = ("category", "name")

    def __str__(self):
        return f"{self.category.name} â€” {self.name}"


class GiftOrder(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gift_orders",
    )
    product = models.ForeignKey(
        GiftProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    order_id = models.CharField(max_length=24, unique=True, editable=False)
    product_name = models.CharField(max_length=160)
    category_name = models.CharField(max_length=100)
    product_image_url = models.URLField(max_length=500, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2)

    recipient_full_name = models.CharField(max_length=150)
    recipient_address = models.TextField()
    recipient_postal_code = models.CharField(max_length=20)
    recipient_country = models.CharField(max_length=100)
    recipient_phone = models.CharField(max_length=30)
    customer_note = models.TextField(blank=True, default="")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    support_email_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="completed_gift_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"PGFT{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def can_mark_completed(self):
        return self.status in {"pending", "processing"}

    @transaction.atomic
    def mark_completed(self, admin_user):
        """Complete once, after admin confirmation; concurrent clicks are safe."""
        locked = GiftOrder.objects.select_for_update().get(pk=self.pk)
        if not locked.can_mark_completed():
            return False

        locked.status = "completed"
        locked.completed_at = timezone.now()
        locked.completed_by = admin_user
        locked.save(update_fields=[
            "status", "completed_at", "completed_by", "updated_at",
        ])

        # Keep the object used by the admin view in sync with the database.
        self.status = locked.status
        self.completed_at = locked.completed_at
        self.completed_by = locked.completed_by
        return True

    def __str__(self):
        return f"{self.order_id} â€” {self.product_name} â€” {self.status}"