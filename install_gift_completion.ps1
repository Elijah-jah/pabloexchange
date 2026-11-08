#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\user\OneDrive\Desktop\PabloExchange"
$BackupRoot = Join-Path $env:USERPROFILE ("PabloExchangeGiftCompletionBackups\" + (Get-Date -Format "yyyyMMdd-HHmmss"))

function Write-Utf8File {
    param([string]$RelativePath, [string]$Content)
    $Destination = Join-Path $ProjectRoot $RelativePath
    $Directory = Split-Path -Parent $Destination
    [System.IO.Directory]::CreateDirectory($Directory) | Out-Null

    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $Backup = Join-Path $BackupRoot $RelativePath
        [System.IO.Directory]::CreateDirectory((Split-Path -Parent $Backup)) | Out-Null
        Copy-Item -LiteralPath $Destination -Destination $Backup -Force
    }

    [System.IO.File]::WriteAllText(
        $Destination,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
    Write-Host "Written: $RelativePath" -ForegroundColor DarkGray
}

function Invoke-Django {
    param([string[]]$Arguments)
    Write-Host "`n> python $($Arguments -join ' ')" -ForegroundColor Cyan
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: python $($Arguments -join ' '). Backups are at $BackupRoot"
    }
}

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot"
}
Set-Location -LiteralPath $ProjectRoot
foreach ($RequiredFile in @("manage.py", "gifts/models.py", "gifts/admin.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $RequiredFile) -PathType Leaf)) {
        throw "Required file not found: $RequiredFile"
    }
}

$Files = [ordered]@{}

$Files['gifts/models.py'] = @'
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
        return f"{self.category.name} — {self.name}"


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
        return f"{self.order_id} — {self.product_name} — {self.status}"
'@

$Files['gifts/admin.py'] = @'
from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import GiftCategory, GiftOrder, GiftProduct
from .services import send_gift_order_email


@admin.register(GiftCategory)
class GiftCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "image_preview", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("name",)

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:44px;height:44px;object-fit:cover;border-radius:8px;">',
                obj.image.url,
            )
        return "—"


@admin.register(GiftProduct)
class GiftProductAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview", "name", "category", "price",
        "display_order", "is_active", "created_at",
    )
    list_filter = ("category", "is_active")
    list_editable = ("price", "display_order", "is_active")
    search_fields = ("name", "description", "category__name")

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:44px;height:44px;object-fit:cover;border-radius:8px;">',
                obj.image.url,
            )
        return "—"


@admin.register(GiftOrder)
class GiftOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id", "product_name", "user", "price", "recipient_full_name",
        "recipient_country", "status", "completion_button",
        "support_email_sent_at", "created_at",
    )
    list_select_related = ("user", "completed_by")
    change_form_template = "admin/gifts/giftorder/change_form.html"
    list_filter = ("status", "category_name", "recipient_country", "created_at")
    search_fields = (
        "order_id", "product_name", "user__username", "user__email",
        "recipient_full_name", "recipient_phone",
    )
    readonly_fields = (
        "order_id", "user", "product", "product_name", "category_name",
        "product_image_url", "price", "recipient_full_name", "recipient_address",
        "recipient_postal_code", "recipient_country", "recipient_phone",
        "customer_note", "support_email_sent_at", "completed_at", "completed_by",
        "created_at", "updated_at",
    )
    actions = ("resend_support_email",)

    @admin.action(description="Resend selected orders to support")
    def resend_support_email(self, request, queryset):
        sent = sum(1 for order in queryset if send_gift_order_email(order.pk))
        self.message_user(request, f"Support email sent for {sent} order(s).")


    def get_urls(self):
        custom_urls = [
            path(
                "<int:order_id>/mark-completed/",
                self.admin_site.admin_view(self.mark_completed_view),
                name="gifts_giftorder_mark_completed",
            ),
        ]
        return custom_urls + super().get_urls()

    @admin.display(description="Completion")
    def completion_button(self, obj):
        if obj.can_mark_completed():
            url = reverse("admin:gifts_giftorder_mark_completed", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="white-space:nowrap;">Mark Completed</a>',
                url,
            )
        if obj.status == "completed":
            return format_html('<span style="color:#047857;font-weight:700;">Completed</span>')
        return "—"

    def mark_completed_view(self, request, order_id):
        order = get_object_or_404(GiftOrder, pk=order_id)

        if request.method == "POST":
            if order.mark_completed(request.user):
                self.message_user(
                    request,
                    f"{order.order_id} has been marked as completed.",
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    f"{order.order_id} was not changed because its current status is {order.get_status_display()}.",
                    messages.WARNING,
                )
            return redirect("admin:gifts_giftorder_change", order.pk)

        context = {
            **self.admin_site.each_context(request),
            "title": f"Confirm completion — {order.order_id}",
            "opts": self.model._meta,
            "order": order,
            "can_complete": order.can_mark_completed(),
        }
        return render(
            request,
            "admin/gifts/giftorder/confirm_completed.html",
            context,
        )
'@

$Files['gifts/templates/admin/gifts/giftorder/confirm_completed.html'] = @'
{% extends "admin/base_site.html" %}

{% block content %}
<div class="module" style="max-width:820px;padding:24px;">
    <h1 style="margin-top:0;">Confirm gift completion</h1>
    <p>
        Check that this is the exact order you received and that the gift has been
        delivered before marking it completed.
    </p>

    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
        <tbody>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Order reference</th><td style="padding:9px;border-bottom:1px solid #ddd;"><strong>{{ order.order_id }}</strong></td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Current status</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.get_status_display }}</td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Gift</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.product_name }}</td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Price</th><td style="padding:9px;border-bottom:1px solid #ddd;">&#8358;{{ order.price|floatformat:2 }}</td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Customer</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.user.username }}{% if order.user.email %} — {{ order.user.email }}{% endif %}</td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Recipient</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.recipient_full_name }}</td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Recipient phone</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.recipient_phone }}</td></tr>
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Delivery address</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.recipient_address|linebreaksbr }}<br>Postal/ZIP: {{ order.recipient_postal_code }}<br>{{ order.recipient_country }}</td></tr>
            {% if order.customer_note %}<tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Customer note</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.customer_note|linebreaksbr }}</td></tr>{% endif %}
            <tr><th style="text-align:left;padding:9px;border-bottom:1px solid #ddd;">Order date</th><td style="padding:9px;border-bottom:1px solid #ddd;">{{ order.created_at }}</td></tr>
        </tbody>
    </table>

    {% if can_complete %}
    <form method="post">
        {% csrf_token %}
        <p><strong>Confirm that {{ order.product_name }} has been delivered to {{ order.recipient_full_name }}.</strong></p>
        <button type="submit" class="default" style="padding:10px 16px;">Yes, Mark as Completed</button>
        <a class="button" href="{% url 'admin:gifts_giftorder_change' order.pk %}" style="margin-left:8px;">Cancel</a>
    </form>
    {% else %}
    <p><strong>This order cannot be marked completed because its status is {{ order.get_status_display }}.</strong></p>
    <a class="button" href="{% url 'admin:gifts_giftorder_change' order.pk %}">Return to order</a>
    {% endif %}
</div>
{% endblock %}
'@

$Files['gifts/templates/admin/gifts/giftorder/change_form.html'] = @'
{% extends "admin/change_form.html" %}

{% block object-tools-items %}
    {{ block.super }}
    {% if original and original.can_mark_completed %}
    <li>
        <a href="{% url 'admin:gifts_giftorder_mark_completed' original.pk %}" class="historylink">
            Mark Completed
        </a>
    </li>
    {% endif %}
{% endblock %}
'@

foreach ($Entry in $Files.GetEnumerator()) {
    Write-Utf8File -RelativePath $Entry.Key -Content $Entry.Value
}

Invoke-Django -Arguments @("manage.py", "check")
Invoke-Django -Arguments @("manage.py", "makemigrations", "gifts")
Invoke-Django -Arguments @("manage.py", "migrate")

Write-Host "`nSafe gift completion is now installed." -ForegroundColor Green
Write-Host "Backups: $BackupRoot" -ForegroundColor DarkGray
Write-Host "`nAdmin usage:" -ForegroundColor Yellow
Write-Host "1. Open Django admin > Gifts > Gift orders."
Write-Host "2. Match the PGFT order reference with the support email."
Write-Host "3. Click Mark Completed and review the recipient and delivery details."
Write-Host "4. Confirm only after the gift has actually been delivered."
