import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class GiftCardCountry(models.Model):
    """A country a gift card is sold for (managed in admin)."""

    name = models.CharField(max_length=100, unique=True)
    flag_emoji = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text='Optional flag shown next to the name, e.g. "US" flag emoji.',
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "Gift card countries"

    def __str__(self):
        return self.name


class GiftCardCategory(models.Model):
    """A gift card category, e.g. Shopping, Gaming, Streaming (managed in admin)."""

    name = models.CharField(max_length=100, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "Gift card categories"

    def __str__(self):
        return self.name


class GiftCard(models.Model):
    """A purchasable gift card. The buyer types any USD amount at purchase time."""

    category = models.ForeignKey(
        GiftCardCategory,
        on_delete=models.PROTECT,
        related_name="cards",
    )
    country = models.ForeignKey(
        GiftCardCountry,
        on_delete=models.PROTECT,
        related_name="cards",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="giftcards/", blank=True, null=True, max_length=255)
    min_amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Smallest card amount the buyer can enter, in USD.",
    )
    max_amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1000.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Largest card amount the buyer can enter, in USD.",
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = ("category", "country", "name")

    def __str__(self):
        return f"{self.name} ({self.country.name})"


class GiftCardOrder(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="giftcard_orders",
    )
    card = models.ForeignKey(
        GiftCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    order_id = models.CharField(max_length=24, unique=True, editable=False)

    # Snapshots so the order survives later card edits/deletions.
    card_name = models.CharField(max_length=160)
    category_name = models.CharField(max_length=100)
    country_name = models.CharField(max_length=100)

    buyer_name = models.CharField(max_length=150)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_ngn = models.DecimalField(max_digits=14, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"PGC{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} \u2014 {self.card_name} \u2014 {self.status}"
