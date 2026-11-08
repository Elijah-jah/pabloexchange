#Requires -Version 5.1
<#
.SYNOPSIS
Installs the complete PabloExchange Gift Sending feature.

Run from PowerShell:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
    .\install_pabloexchange_gifts.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\user\OneDrive\Desktop\Pabloexchange"
$BackupRoot = Join-Path $env:USERPROFILE ("PabloExchangeGiftBackups\" + (Get-Date -Format "yyyyMMdd-HHmmss"))

function Backup-File {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $Source = Join-Path $ProjectRoot $RelativePath
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        $Backup = Join-Path $BackupRoot $RelativePath
        $BackupDirectory = Split-Path -Parent $Backup
        [System.IO.Directory]::CreateDirectory($BackupDirectory) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Backup -Force
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )

    $Destination = Join-Path $ProjectRoot $RelativePath
    $Directory = Split-Path -Parent $Destination
    [System.IO.Directory]::CreateDirectory($Directory) | Out-Null
    Backup-File -RelativePath $RelativePath
    [System.IO.File]::WriteAllText(
        $Destination,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
    Write-Host "Written: $RelativePath" -ForegroundColor DarkGray
}

function Invoke-Django {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    Write-Host "`n> python $($Arguments -join ' ')" -ForegroundColor Cyan
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: python $($Arguments -join ' '). Existing changed files are backed up at $BackupRoot"
    }
}

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot. Update `$ProjectRoot at the top of this script."
}
Set-Location -LiteralPath $ProjectRoot

$RequiredFiles = @(
    "manage.py",
    "config/settings.py",
    "config/urls.py",
    "smsmarket/views.py",
    "static/css/purchases.css"
)
foreach ($RequiredFile in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $RequiredFile) -PathType Leaf)) {
        throw "Required file not found: $RequiredFile. Run this installer against the PabloExchange project root."
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "gifts") -PathType Container)) {
    throw "The gifts app folder is missing. Create the app scaffold first, then rerun this installer."
}

$SettingsPreview = [System.IO.File]::ReadAllText((Join-Path $ProjectRoot "config/settings.py"))
$GiftAppTokens = @('"gifts"', "'gifts'", '"gifts.apps.GiftsConfig"', "'gifts.apps.GiftsConfig'")
$GiftAppInstalled = $false
foreach ($Token in $GiftAppTokens) {
    if ($SettingsPreview.Contains($Token)) {
        $GiftAppInstalled = $true
        break
    }
}
if (-not $GiftAppInstalled) {
    throw "Add 'gifts' to INSTALLED_APPS in config/settings.py, then rerun this installer. No files were changed."
}

Write-Host "Installing PabloExchange Gift Sending..." -ForegroundColor Green
Write-Host "Project: $ProjectRoot"

$Files = [ordered]@{}

$Files['gifts/models.py'] = @'
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"PGFT{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} — {self.product_name} — {self.status}"
'@

$Files['gifts/forms.py'] = @'
import re

from django import forms

from .models import GiftOrder


class GiftOrderForm(forms.ModelForm):
    class Meta:
        model = GiftOrder
        fields = (
            "recipient_full_name",
            "recipient_address",
            "recipient_postal_code",
            "recipient_country",
            "recipient_phone",
            "customer_note",
        )
        labels = {
            "recipient_full_name": "Recipient's full name",
            "recipient_address": "Complete delivery address",
            "recipient_postal_code": "Postal / ZIP code",
            "recipient_country": "Country",
            "recipient_phone": "Recipient's phone number",
            "customer_note": "Delivery note (optional)",
        }
        widgets = {
            "recipient_address": forms.Textarea(attrs={"rows": 3}),
            "customer_note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "recipient_full_name": "e.g. Adaeze Okafor",
            "recipient_address": "House number, street, city and state",
            "recipient_postal_code": "e.g. 100001",
            "recipient_country": "e.g. Nigeria",
            "recipient_phone": "e.g. +234 800 000 0000",
            "customer_note": "Anything support should know about this delivery",
        }
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "gift-control"
            field.widget.attrs["placeholder"] = placeholders.get(name, "")
        self.fields["recipient_phone"].widget.attrs["inputmode"] = "tel"

    def clean_recipient_phone(self):
        value = " ".join(self.cleaned_data["recipient_phone"].split())
        if not re.fullmatch(r"^\+?[0-9()\s-]{7,25}$", value):
            raise forms.ValidationError("Enter a valid phone number, including the country code.")
        return value

    def clean_recipient_full_name(self):
        value = " ".join(self.cleaned_data["recipient_full_name"].split())
        if len(value.split()) < 2:
            raise forms.ValidationError("Enter the recipient's first and last name.")
        return value
'@

$Files['gifts/services.py'] = @'
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from wallet.services import balance as get_balance, can_afford, debit

from .models import GiftOrder, GiftProduct

logger = logging.getLogger(__name__)


class GiftOrderError(Exception):
    pass


def send_gift_order_email(order_pk):
    """Send a saved order to support. A mail failure never removes the order."""
    try:
        order = GiftOrder.objects.select_related("user").get(pk=order_pk)
    except GiftOrder.DoesNotExist:
        return False

    support_email = (
        getattr(settings, "SUPPORT_EMAIL", "")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not support_email:
        logger.error("Gift order %s has no SUPPORT_EMAIL configured", order.order_id)
        return False

    subject = f"New gift order {order.order_id} — {order.product_name}"
    message = f"""A new gift order has been placed on PabloExchange.

ORDER
Order reference: {order.order_id}
Status: {order.get_status_display()}
Product: {order.product_name}
Category: {order.category_name}
Price: NGN {order.price:,.2f}
Placed: {order.created_at:%B %d, %Y at %H:%M}

CUSTOMER
Username: {order.user.username}
Email: {order.user.email or 'Not provided'}

RECIPIENT
Full name: {order.recipient_full_name}
Address: {order.recipient_address}
Postal / ZIP code: {order.recipient_postal_code}
Country: {order.recipient_country}
Phone: {order.recipient_phone}
Delivery note: {order.customer_note or 'None'}

Open Django admin → Gifts → Gift orders to process this order.
"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[support_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Support email failed for gift order %s", order.order_id)
        return False

    GiftOrder.objects.filter(pk=order.pk).update(
        support_email_sent_at=timezone.now()
    )
    return True


@transaction.atomic
def create_gift_order(user, product_id, recipient_data):
    product = (
        GiftProduct.objects.select_for_update()
        .select_related("category")
        .filter(pk=product_id, is_active=True, category__is_active=True)
        .first()
    )
    if product is None:
        raise GiftOrderError("This gift is no longer available.")

    if not can_afford(user, product.price):
        balance = get_balance(user)
        raise GiftOrderError(
            f"Insufficient balance. This gift costs ₦{product.price:,.2f}, "
            f"but your wallet balance is ₦{balance:,.2f}."
        )

    image_url = ""
    if product.image:
        try:
            image_url = product.image.url
        except (ValueError, AttributeError):
            image_url = ""

    order = GiftOrder.objects.create(
        user=user,
        product=product,
        product_name=product.name,
        category_name=product.category.name,
        product_image_url=image_url,
        price=product.price,
        status="pending",
        **recipient_data,
    )

    try:
        debit(
            user,
            product.price,
            description=f"Gift order {order.order_id} — {product.name}",
            meta={"gift_order_id": order.id, "order_id": order.order_id},
        )
    except Exception as exc:
        logger.exception("Wallet charge failed for gift order %s", order.order_id)
        raise GiftOrderError(
            "We could not complete the wallet charge. No gift order was placed; please try again."
        ) from exc

    transaction.on_commit(
        lambda order_pk=order.pk: send_gift_order_email(order_pk)
    )
    return order
'@

$Files['gifts/views.py'] = @'
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from wallet.services import balance as get_balance

from .forms import GiftOrderForm
from .models import GiftCategory, GiftProduct
from .services import GiftOrderError, create_gift_order


@login_required
def gift_sending(request):
    products = GiftProduct.objects.filter(is_active=True).select_related("category")
    categories = (
        GiftCategory.objects.filter(is_active=True, products__is_active=True)
        .distinct()
        .prefetch_related(Prefetch("products", queryset=products))
    )
    return render(request, "gifts/gift_sending.html", {
        "categories": categories,
        "balance": get_balance(request.user),
    })


@login_required
@require_POST
def gift_order_create(request, product_id):
    form = GiftOrderForm(request.POST)
    if not form.is_valid():
        errors = {
            field: [item["message"] for item in messages]
            for field, messages in form.errors.get_json_data().items()
        }
        return JsonResponse({
            "success": False,
            "error": "Please correct the highlighted recipient details.",
            "errors": errors,
        }, status=400)

    try:
        order = create_gift_order(
            user=request.user,
            product_id=product_id,
            recipient_data=form.cleaned_data,
        )
    except GiftOrderError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse({
        "success": True,
        "order_id": order.order_id,
        "product_name": order.product_name,
        "status": order.status,
        "new_balance": str(get_balance(request.user)),
        "message": "Your gift order has been placed and is now pending.",
    })
'@

$Files['gifts/urls.py'] = @'
from django.urls import path

from . import views


urlpatterns = [
    path("gifts/", views.gift_sending, name="gift_sending"),
    path(
        "gifts/order/<int:product_id>/",
        views.gift_order_create,
        name="gift_order_create",
    ),
]
'@

$Files['gifts/admin.py'] = @'
from django.contrib import admin
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
        "recipient_country", "status", "support_email_sent_at", "created_at",
    )
    list_filter = ("status", "category_name", "recipient_country", "created_at")
    search_fields = (
        "order_id", "product_name", "user__username", "user__email",
        "recipient_full_name", "recipient_phone",
    )
    readonly_fields = (
        "order_id", "user", "product", "product_name", "category_name",
        "product_image_url", "price", "recipient_full_name", "recipient_address",
        "recipient_postal_code", "recipient_country", "recipient_phone",
        "customer_note", "support_email_sent_at", "created_at", "updated_at",
    )
    actions = ("resend_support_email",)

    @admin.action(description="Resend selected orders to support")
    def resend_support_email(self, request, queryset):
        sent = sum(1 for order in queryset if send_gift_order_email(order.pk))
        self.message_user(request, f"Support email sent for {sent} order(s).")
'@

$Files['gifts/templates/gifts/gift_sending.html'] = @'
{% extends "base.html" %}
{% load static humanize %}

{% block title %}Gift Sending{% endblock %}
{% block page_title %}Gift Sending{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'gifts/css/gift_sending.css' %}?v=1">
{% endblock %}

{% block content %}
<div class="gift-page">
    <section class="gift-hero">
        <div class="gift-hero-copy">
            <span class="gift-eyebrow"><i class="bi bi-stars"></i> PabloExchange Gifts</span>
            <h1>Send something thoughtful.</h1>
            <p>Choose a gift, provide the recipient’s delivery details, and our support team will process your order.</p>
        </div>
        <div class="gift-balance-card">
            <span><i class="bi bi-wallet2"></i> Available balance</span>
            <strong id="giftWalletBalance">₦{{ balance|floatformat:2|intcomma }}</strong>
            <a href="{% url 'wallet:fund' %}">Fund wallet <i class="bi bi-arrow-right"></i></a>
        </div>
    </section>

    {% if categories %}
    <div class="gift-filters" aria-label="Filter gift categories">
        <button type="button" class="gift-filter active" data-filter="all">
            <i class="bi bi-grid"></i> All gifts
        </button>
        {% for category in categories %}
        <button type="button" class="gift-filter" data-filter="category-{{ category.id }}">
            {{ category.name }}
        </button>
        {% endfor %}
    </div>

    <div class="gift-sections">
        {% for category in categories %}
        <section class="gift-section" id="category-{{ category.id }}">
            <div class="gift-section-head">
                {% if category.image %}
                <img src="{{ category.image.url }}" alt="" class="gift-category-image">
                {% else %}
                <span class="gift-category-icon"><i class="bi bi-gift"></i></span>
                {% endif %}
                <div>
                    <h2>{{ category.name }}</h2>
                    {% if category.description %}<p>{{ category.description }}</p>{% endif %}
                </div>
                <span class="gift-count">{{ category.products.all|length }} item{{ category.products.all|length|pluralize }}</span>
            </div>

            <div class="gift-grid">
                {% for product in category.products.all %}
                <article class="gift-card">
                    <div class="gift-product-media">
                        {% if product.image %}
                        <img src="{{ product.image.url }}" alt="{{ product.name }}" loading="lazy">
                        {% else %}
                        <div class="gift-image-fallback"><i class="bi bi-gift"></i></div>
                        {% endif %}
                        <span class="gift-category-badge">{{ category.name }}</span>
                    </div>
                    <div class="gift-card-body">
                        <h3>{{ product.name }}</h3>
                        {% if product.description %}<p>{{ product.description }}</p>{% endif %}
                        <div class="gift-card-footer">
                            <div class="gift-price">
                                <span>Price</span>
                                <strong>₦{{ product.price|floatformat:2|intcomma }}</strong>
                            </div>
                            <button
                                type="button"
                                class="gift-send"
                                data-order-url="{% url 'gift_order_create' product.id %}"
                                data-product-name="{{ product.name }}"
                                data-price="{{ product.price }}"
                                data-image="{% if product.image %}{{ product.image.url }}{% endif %}"
                                aria-label="Send {{ product.name }} as a gift">
                                <i class="bi bi-send"></i> Send Gift
                            </button>
                        </div>
                    </div>
                </article>
                {% endfor %}
            </div>
        </section>
        {% endfor %}
    </div>
    {% else %}
    <div class="gift-empty">
        <span><i class="bi bi-gift"></i></span>
        <h2>No gifts available yet</h2>
        <p>Please check back soon or contact support if you need help.</p>
    </div>
    {% endif %}

    <aside class="gift-support">
        <span class="gift-support-icon"><i class="bi bi-telegram"></i></span>
        <div>
            <h2>Need help with a gift order?</h2>
            <p>If you do not understand anything on this page, contact our support team before placing your order.</p>
        </div>
        <a href="https://t.me/Pabloexchange1" target="_blank" rel="noopener noreferrer">
            <i class="bi bi-telegram"></i> Contact support
        </a>
    </aside>
</div>

<div class="gift-modal" id="giftOrderModal" hidden>
    <div class="gift-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="giftModalTitle">
        <button type="button" class="gift-modal-close" data-close-order aria-label="Close">
            <i class="bi bi-x-lg"></i>
        </button>
        <div class="gift-modal-heading">
            <span><i class="bi bi-box2-heart"></i></span>
            <div>
                <p>Recipient details</p>
                <h2 id="giftModalTitle">Confirm your gift order</h2>
            </div>
        </div>

        <div class="gift-order-summary">
            <img id="giftSummaryImage" src="" alt="" hidden>
            <span class="gift-summary-fallback" id="giftSummaryFallback"><i class="bi bi-gift"></i></span>
            <div>
                <strong id="giftSummaryName"></strong>
                <span>Amount charged to your wallet</span>
            </div>
            <b id="giftSummaryPrice"></b>
        </div>

        <form id="giftOrderForm" method="post" novalidate>
            {% csrf_token %}
            <div class="gift-form-alert" id="giftFormAlert" role="alert" hidden></div>

            <div class="gift-form-grid">
                <div class="gift-field gift-field-full">
                    <label for="recipient_full_name">Recipient’s full name</label>
                    <input class="gift-control" id="recipient_full_name" name="recipient_full_name" maxlength="150" autocomplete="name" placeholder="First and last name" required>
                    <span class="gift-field-error" data-field="recipient_full_name"></span>
                </div>

                <div class="gift-field gift-field-full">
                    <label for="recipient_address">Complete delivery address</label>
                    <textarea class="gift-control" id="recipient_address" name="recipient_address" rows="3" placeholder="House number, street, city and state" required></textarea>
                    <span class="gift-field-error" data-field="recipient_address"></span>
                </div>

                <div class="gift-field">
                    <label for="recipient_postal_code">Postal / ZIP code</label>
                    <input class="gift-control" id="recipient_postal_code" name="recipient_postal_code" maxlength="20" placeholder="e.g. 100001" required>
                    <span class="gift-field-error" data-field="recipient_postal_code"></span>
                </div>

                <div class="gift-field">
                    <label for="recipient_country">Country</label>
                    <input class="gift-control" id="recipient_country" name="recipient_country" maxlength="100" autocomplete="country-name" placeholder="e.g. Nigeria" required>
                    <span class="gift-field-error" data-field="recipient_country"></span>
                </div>

                <div class="gift-field gift-field-full">
                    <label for="recipient_phone">Recipient’s phone number</label>
                    <input class="gift-control" id="recipient_phone" name="recipient_phone" type="tel" maxlength="30" inputmode="tel" autocomplete="tel" placeholder="Include the country code" required>
                    <span class="gift-field-error" data-field="recipient_phone"></span>
                </div>

                <div class="gift-field gift-field-full">
                    <label for="customer_note">Delivery note <em>Optional</em></label>
                    <textarea class="gift-control" id="customer_note" name="customer_note" rows="2" placeholder="Anything support should know about this delivery"></textarea>
                    <span class="gift-field-error" data-field="customer_note"></span>
                </div>
            </div>

            <p class="gift-charge-note"><i class="bi bi-shield-check"></i> Your wallet will be charged only after these details pass validation.</p>

            <div class="gift-modal-actions">
                <button type="button" class="gift-btn-secondary" data-close-order>Cancel</button>
                <button type="submit" class="gift-btn-primary" id="giftSubmitButton">
                    <i class="bi bi-check2-circle"></i> <span>Confirm &amp; Pay</span>
                </button>
            </div>
        </form>
    </div>
</div>

<div class="gift-modal" id="giftSuccessModal" hidden>
    <div class="gift-success-dialog" role="dialog" aria-modal="true" aria-labelledby="giftSuccessTitle">
        <span class="gift-success-icon"><i class="bi bi-check2"></i></span>
        <p class="gift-success-kicker">Order received</p>
        <h2 id="giftSuccessTitle">Your gift order is pending</h2>
        <p>Support has received the order details and will process the delivery. You can follow its status in My Purchases.</p>
        <div class="gift-success-details">
            <div><span>Order reference</span><strong id="giftSuccessOrder"></strong></div>
            <div><span>Gift</span><strong id="giftSuccessProduct"></strong></div>
            <div><span>Status</span><strong class="gift-pending">Pending</strong></div>
        </div>
        <a href="{% url 'smsmarket:my_purchases' %}" class="gift-btn-primary gift-success-link">
            <i class="bi bi-bag-check"></i> View My Purchases
        </a>
        <button type="button" class="gift-btn-secondary gift-success-close" id="giftSuccessClose">Continue shopping</button>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'gifts/js/gift_sending.js' %}?v=1"></script>
{% endblock %}
'@

$Files['gifts/static/gifts/js/gift_sending.js'] = @'
(function () {
    "use strict";

    var modal = document.getElementById("giftOrderModal");
    var form = document.getElementById("giftOrderForm");
    if (!modal || !form) return;

    var successModal = document.getElementById("giftSuccessModal");
    var submitButton = document.getElementById("giftSubmitButton");
    var alertBox = document.getElementById("giftFormAlert");
    var activeCard = null;
    var lastFocused = null;

    function naira(value) {
        return "₦" + parseFloat(value || "0").toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function clearErrors() {
        alertBox.hidden = true;
        alertBox.textContent = "";
        form.querySelectorAll(".gift-field-error").forEach(function (el) {
            el.textContent = "";
        });
        form.querySelectorAll(".gift-control").forEach(function (el) {
            el.classList.remove("has-error");
        });
    }

    function showError(message) {
        alertBox.textContent = message || "We could not place your order. Please try again.";
        alertBox.hidden = false;
        alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function openOrderModal(button) {
        activeCard = button;
        lastFocused = document.activeElement;
        clearErrors();
        form.reset();

        var imageUrl = button.getAttribute("data-image") || "";
        var image = document.getElementById("giftSummaryImage");
        var fallback = document.getElementById("giftSummaryFallback");
        if (imageUrl) {
            image.src = imageUrl;
            image.hidden = false;
            fallback.hidden = true;
        } else {
            image.src = "";
            image.hidden = true;
            fallback.hidden = false;
        }

        document.getElementById("giftSummaryName").textContent = button.getAttribute("data-product-name");
        document.getElementById("giftSummaryPrice").textContent = naira(button.getAttribute("data-price"));
        modal.hidden = false;
        document.body.style.overflow = "hidden";
        setTimeout(function () {
            document.getElementById("recipient_full_name").focus();
        }, 30);
    }

    function closeOrderModal() {
        modal.hidden = true;
        document.body.style.overflow = "";
        activeCard = null;
        if (lastFocused) lastFocused.focus();
    }

    function closeSuccessModal() {
        successModal.hidden = true;
        document.body.style.overflow = "";
    }

    document.querySelectorAll(".gift-send").forEach(function (button) {
        button.addEventListener("click", function () { openOrderModal(button); });
    });

    document.querySelectorAll("[data-close-order]").forEach(function (button) {
        button.addEventListener("click", closeOrderModal);
    });

    modal.addEventListener("click", function (event) {
        if (event.target === modal) closeOrderModal();
    });

    successModal.addEventListener("click", function (event) {
        if (event.target === successModal) closeSuccessModal();
    });
    document.getElementById("giftSuccessClose").addEventListener("click", closeSuccessModal);

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        if (!modal.hidden) closeOrderModal();
        if (!successModal.hidden) closeSuccessModal();
    });

    document.querySelectorAll(".gift-filter").forEach(function (button) {
        button.addEventListener("click", function () {
            document.querySelectorAll(".gift-filter").forEach(function (item) {
                item.classList.remove("active");
            });
            button.classList.add("active");
            var filter = button.getAttribute("data-filter");
            document.querySelectorAll(".gift-section").forEach(function (section) {
                section.hidden = filter !== "all" && section.id !== filter;
            });
        });
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!activeCard || submitButton.disabled) return;
        clearErrors();

        if (!form.checkValidity()) {
            form.reportValidity();
            showError("Please complete all required recipient details.");
            return;
        }

        submitButton.disabled = true;
        submitButton.querySelector("span").textContent = "Placing order…";

        fetch(activeCard.getAttribute("data-order-url"), {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
        })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            var data = result.data;
            if (!result.ok || !data.success) {
                showError(data.error);
                if (data.errors) {
                    Object.keys(data.errors).forEach(function (field) {
                        var target = form.querySelector('[data-field="' + field + '"]');
                        var input = form.querySelector('[name="' + field + '"]');
                        if (target) target.textContent = data.errors[field].join(" ");
                        if (input) input.classList.add("has-error");
                    });
                }
                return;
            }

            var newBalance = naira(data.new_balance);
            document.querySelectorAll(".wallet-amount, .wallet-chip .mono, #giftWalletBalance")
                .forEach(function (element) { element.textContent = newBalance; });

            document.getElementById("giftSuccessOrder").textContent = data.order_id;
            document.getElementById("giftSuccessProduct").textContent = data.product_name;
            closeOrderModal();
            successModal.hidden = false;
            document.body.style.overflow = "hidden";
        })
        .catch(function () {
            showError("Network error. Please check your connection and try again.");
        })
        .finally(function () {
            submitButton.disabled = false;
            submitButton.querySelector("span").textContent = "Confirm & Pay";
        });
    });
})();
'@

$Files['gifts/static/gifts/css/gift_sending.css'] = @'
/* PabloExchange Gift Sending — responsive catalog and checkout */
.gift-page {
    --gift-green: #047857;
    --gift-green-2: #059669;
    --gift-dark: #022c22;
    --gift-gold: #f0b429;
    --gift-text: #12211c;
    --gift-muted: #62756e;
    --gift-border: #e0ebe6;
    width: 100%;
    max-width: 1240px;
    margin: 0 auto;
}

.gift-page *, .gift-modal * { box-sizing: border-box; }
.gift-page button, .gift-modal button { font: inherit; }
.gift-modal[hidden], .gift-page [hidden] { display: none !important; }

.gift-hero {
    position: relative;
    overflow: hidden;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 28px;
    padding: clamp(24px, 4vw, 42px);
    border-radius: 22px;
    color: #fff;
    background:
        radial-gradient(circle at 88% 5%, rgba(240, 180, 41, .24), transparent 34%),
        linear-gradient(125deg, #022c22, #075b46);
    box-shadow: 0 16px 40px rgba(2, 44, 34, .15);
}
.gift-hero::after {
    content: "\F51C";
    position: absolute;
    right: 27%;
    bottom: -42px;
    font-family: "bootstrap-icons";
    font-size: 180px;
    color: rgba(255, 255, 255, .035);
    transform: rotate(-10deg);
    pointer-events: none;
}
.gift-hero-copy { position: relative; z-index: 1; min-width: 0; }
.gift-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 12px;
    color: #f8cf69;
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .09em;
    text-transform: uppercase;
}
.gift-hero h1 {
    margin: 0;
    font-size: clamp(1.8rem, 4vw, 3rem);
    line-height: 1.08;
    letter-spacing: -.04em;
    font-weight: 800;
}
.gift-hero-copy > p {
    max-width: 620px;
    margin: 13px 0 0;
    color: #c4d9d1;
    font-size: clamp(.88rem, 1.5vw, 1rem);
    line-height: 1.65;
}
.gift-balance-card {
    position: relative;
    z-index: 1;
    min-width: 210px;
    padding: 19px 22px;
    border: 1px solid rgba(255, 255, 255, .15);
    border-radius: 16px;
    background: rgba(255, 255, 255, .08);
    backdrop-filter: blur(8px);
}
.gift-balance-card > span {
    display: flex;
    align-items: center;
    gap: 7px;
    color: #c4d9d1;
    font-size: .76rem;
}
.gift-balance-card strong {
    display: block;
    margin: 7px 0 9px;
    color: #fff;
    font-size: 1.45rem;
    font-variant-numeric: tabular-nums;
}
.gift-balance-card a {
    color: #f8cf69;
    font-size: .78rem;
    font-weight: 700;
    text-decoration: none;
}

.gift-filters {
    display: flex;
    gap: 8px;
    margin: 25px 0 22px;
    padding-bottom: 4px;
    overflow-x: auto;
    scrollbar-width: thin;
}
.gift-filter {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 16px;
    border: 1px solid var(--gift-border);
    border-radius: 999px;
    background: #fff;
    color: var(--gift-muted);
    font-size: .82rem;
    font-weight: 700;
    cursor: pointer;
}
.gift-filter:hover { border-color: var(--gift-green-2); color: var(--gift-green); }
.gift-filter.active {
    border-color: transparent;
    background: var(--gift-dark);
    color: #fff;
}

.gift-sections { display: grid; gap: 30px; }
.gift-section-head {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
}
.gift-category-image, .gift-category-icon {
    width: 45px;
    height: 45px;
    flex: 0 0 auto;
    border-radius: 13px;
}
.gift-category-image { object-fit: cover; border: 1px solid var(--gift-border); }
.gift-category-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #e9f8f2;
    color: var(--gift-green);
    font-size: 1.2rem;
}
.gift-section-head h2 { margin: 0; color: var(--gift-text); font-size: 1.08rem; font-weight: 800; }
.gift-section-head p { margin: 3px 0 0; color: var(--gift-muted); font-size: .8rem; }
.gift-count {
    margin-left: auto;
    padding: 4px 10px;
    border-radius: 999px;
    background: #edf5f1;
    color: var(--gift-muted);
    font-size: .72rem;
    white-space: nowrap;
}

.gift-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 245px), 1fr));
    gap: 17px;
}
.gift-card {
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    border: 1px solid var(--gift-border);
    border-radius: 17px;
    background: #fff;
    box-shadow: 0 5px 18px rgba(2, 44, 34, .05);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.gift-card:hover {
    transform: translateY(-3px);
    border-color: #b9d9cc;
    box-shadow: 0 13px 28px rgba(2, 44, 34, .10);
}
.gift-product-media { position: relative; aspect-ratio: 4 / 3; background: #edf5f1; overflow: hidden; }
.gift-product-media > img { width: 100%; height: 100%; display: block; object-fit: cover; transition: transform .3s ease; }
.gift-card:hover .gift-product-media > img { transform: scale(1.025); }
.gift-image-fallback {
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    color: #8cb9a8; font-size: 3.4rem;
    background: linear-gradient(135deg, #f2faf6, #dfeee8);
}
.gift-category-badge {
    position: absolute;
    left: 12px;
    top: 12px;
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(2, 44, 34, .83);
    color: #fff;
    font-size: .66rem;
    font-weight: 700;
    backdrop-filter: blur(6px);
}
.gift-card-body { display: flex; flex: 1; flex-direction: column; padding: 17px; }
.gift-card-body h3 { margin: 0; color: var(--gift-text); font-size: .98rem; line-height: 1.35; font-weight: 800; }
.gift-card-body > p {
    margin: 8px 0 17px;
    color: var(--gift-muted);
    font-size: .8rem;
    line-height: 1.55;
    overflow-wrap: anywhere;
}
.gift-card-footer {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
    margin-top: auto;
    padding-top: 15px;
    border-top: 1px solid #edf3f0;
}
.gift-price span { display: block; color: var(--gift-muted); font-size: .66rem; }
.gift-price strong { display: block; margin-top: 3px; color: var(--gift-green); font-size: 1.02rem; font-variant-numeric: tabular-nums; }
.gift-send {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 9px 13px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, var(--gift-green), var(--gift-green-2));
    color: #fff;
    font-size: .76rem;
    font-weight: 800;
    cursor: pointer;
    white-space: nowrap;
}
.gift-send:hover { filter: brightness(1.07); }

.gift-empty {
    padding: 60px 20px;
    border: 1px dashed #c8ddd4;
    border-radius: 18px;
    background: #fff;
    text-align: center;
}
.gift-empty > span { color: var(--gift-green); font-size: 2.3rem; }
.gift-empty h2 { margin: 12px 0 5px; font-size: 1.1rem; }
.gift-empty p { margin: 0; color: var(--gift-muted); font-size: .86rem; }

.gift-support {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 15px;
    margin-top: 30px;
    padding: 18px 20px;
    border: 1px solid #d8e9f8;
    border-radius: 16px;
    background: #f2f9ff;
}
.gift-support-icon {
    width: 43px; height: 43px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%; background: #229ed9; color: #fff; font-size: 1.25rem;
}
.gift-support h2 { margin: 0; color: #173f5f; font-size: .94rem; font-weight: 800; }
.gift-support p { margin: 4px 0 0; color: #5f7c93; font-size: .79rem; line-height: 1.5; }
.gift-support > a {
    display: inline-flex; align-items: center; justify-content: center; gap: 7px;
    padding: 10px 15px; border-radius: 10px;
    background: #229ed9; color: #fff; text-decoration: none;
    font-size: .78rem; font-weight: 800; white-space: nowrap;
}

/* Checkout modal */
.gift-modal {
    position: fixed;
    inset: 0;
    z-index: 5000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 18px;
    background: rgba(2, 28, 22, .68);
    backdrop-filter: blur(5px);
}
.gift-modal-dialog, .gift-success-dialog {
    position: relative;
    width: min(100%, 650px);
    max-height: calc(100dvh - 36px);
    overflow-y: auto;
    overscroll-behavior: contain;
    border-radius: 20px;
    background: #fff;
    box-shadow: 0 28px 80px rgba(0, 0, 0, .30);
}
.gift-modal-dialog { padding: clamp(20px, 3vw, 29px); }
.gift-modal-close {
    position: absolute;
    right: 15px; top: 15px;
    width: 34px; height: 34px;
    display: flex; align-items: center; justify-content: center;
    border: none; border-radius: 50%; background: #f0f5f3; color: #567068; cursor: pointer;
}
.gift-modal-heading { display: flex; align-items: center; gap: 11px; padding-right: 38px; }
.gift-modal-heading > span {
    width: 43px; height: 43px; flex: 0 0 auto;
    display: flex; align-items: center; justify-content: center;
    border-radius: 13px; background: #e9f8f2; color: #047857; font-size: 1.25rem;
}
.gift-modal-heading p { margin: 0 0 2px; color: #71867e; font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; font-weight: 800; }
.gift-modal-heading h2 { margin: 0; color: #12211c; font-size: 1.12rem; font-weight: 800; }

.gift-order-summary {
    display: flex;
    align-items: center;
    gap: 11px;
    margin: 20px 0;
    padding: 12px;
    border: 1px solid #e1ece7;
    border-radius: 13px;
    background: #f7fbf9;
}
.gift-order-summary img, .gift-summary-fallback {
    width: 47px; height: 47px; flex: 0 0 auto; border-radius: 11px;
}
.gift-order-summary img { object-fit: cover; }
.gift-summary-fallback { display: flex; align-items: center; justify-content: center; background: #dfeee8; color: #047857; font-size: 1.25rem; }
.gift-order-summary > div { min-width: 0; flex: 1; }
.gift-order-summary strong { display: block; color: #12211c; font-size: .85rem; overflow-wrap: anywhere; }
.gift-order-summary span { display: block; margin-top: 3px; color: #71867e; font-size: .69rem; }
.gift-order-summary > b { color: #047857; font-size: .92rem; white-space: nowrap; }

.gift-form-alert {
    margin-bottom: 15px;
    padding: 11px 13px;
    border: 1px solid #fecaca;
    border-radius: 10px;
    background: #fef2f2;
    color: #b91c1c;
    font-size: .8rem;
    line-height: 1.5;
}
.gift-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.gift-field { min-width: 0; }
.gift-field-full { grid-column: 1 / -1; }
.gift-field label { display: flex; justify-content: space-between; margin-bottom: 6px; color: #344b42; font-size: .75rem; font-weight: 700; }
.gift-field label em { color: #8aa098; font-size: .68rem; font-style: normal; font-weight: 500; }
.gift-control {
    width: 100%;
    min-width: 0;
    padding: 11px 12px;
    border: 1px solid #dce8e2;
    border-radius: 10px;
    outline: none;
    background: #fff;
    color: #12211c;
    font-family: inherit;
    font-size: .85rem;
    line-height: 1.45;
    transition: border-color .15s, box-shadow .15s;
}
textarea.gift-control { resize: vertical; min-height: 70px; }
.gift-control:focus { border-color: #059669; box-shadow: 0 0 0 3px rgba(5, 150, 105, .12); }
.gift-control.has-error { border-color: #dc2626; }
.gift-field-error { display: block; min-height: 0; margin-top: 4px; color: #b91c1c; font-size: .69rem; }
.gift-field-error:empty { display: none; }
.gift-charge-note { display: flex; align-items: flex-start; gap: 6px; margin: 15px 0 0; color: #71867e; font-size: .71rem; line-height: 1.5; }
.gift-charge-note i { color: #047857; margin-top: 2px; }
.gift-modal-actions { display: flex; justify-content: flex-end; gap: 9px; margin-top: 20px; }
.gift-btn-primary, .gift-btn-secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-height: 43px;
    padding: 10px 17px;
    border-radius: 11px;
    font-size: .8rem;
    font-weight: 800;
    text-decoration: none;
    cursor: pointer;
}
.gift-btn-primary { border: none; background: linear-gradient(135deg, #047857, #059669); color: #fff; }
.gift-btn-secondary { border: 1px solid #dce8e2; background: #fff; color: #526a61; }
.gift-btn-primary:disabled { opacity: .65; cursor: wait; }

.gift-success-dialog { width: min(100%, 440px); padding: 30px; text-align: center; }
.gift-success-icon {
    width: 62px; height: 62px; margin: 0 auto 15px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%; background: #d1fae5; color: #047857; font-size: 2rem;
}
.gift-success-kicker { margin: 0 0 5px; color: #047857; font-size: .69rem; font-weight: 800; text-transform: uppercase; letter-spacing: .09em; }
.gift-success-dialog h2 { margin: 0; color: #12211c; font-size: 1.25rem; }
.gift-success-dialog > p:not(.gift-success-kicker) { margin: 10px 0 18px; color: #62756e; font-size: .8rem; line-height: 1.6; }
.gift-success-details { padding: 6px 14px; border-radius: 12px; background: #f4f8f6; text-align: left; }
.gift-success-details > div { display: flex; justify-content: space-between; gap: 15px; padding: 10px 0; border-bottom: 1px solid #e1ebe6; font-size: .76rem; }
.gift-success-details > div:last-child { border-bottom: none; }
.gift-success-details span { color: #71867e; }
.gift-success-details strong { color: #12211c; text-align: right; overflow-wrap: anywhere; }
.gift-success-details .gift-pending { color: #a16207; }
.gift-success-link { width: 100%; margin-top: 18px; }
.gift-success-close { width: 100%; margin-top: 8px; }

@media (max-width: 760px) {
    .gift-hero { grid-template-columns: 1fr; gap: 20px; }
    .gift-balance-card { min-width: 0; width: 100%; }
    .gift-support { grid-template-columns: auto minmax(0, 1fr); }
    .gift-support > a { grid-column: 1 / -1; width: 100%; }
}

@media (max-width: 560px) {
    .gift-hero { padding: 23px 19px; border-radius: 17px; }
    .gift-hero h1 { font-size: 1.85rem; }
    .gift-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; }
    .gift-card { border-radius: 13px; }
    .gift-card-body { padding: 12px; }
    .gift-card-body h3 { font-size: .85rem; }
    .gift-card-body > p { font-size: .73rem; }
    .gift-card-footer { align-items: stretch; flex-direction: column; gap: 9px; }
    .gift-send { width: 100%; }
    .gift-section-head { align-items: flex-start; }
    .gift-count { display: none; }
    .gift-modal { padding: 10px; align-items: flex-end; }
    .gift-modal-dialog, .gift-success-dialog { max-height: calc(100dvh - 20px); border-radius: 18px; }
    .gift-form-grid { grid-template-columns: 1fr; }
    .gift-field-full { grid-column: auto; }
    .gift-control { font-size: 16px; }
    .gift-modal-actions { display: grid; grid-template-columns: 1fr 1.5fr; }
    .gift-modal-actions button { width: 100%; }
}

@media (max-width: 350px) {
    .gift-grid { grid-template-columns: 1fr; }
    .gift-modal-actions { grid-template-columns: 1fr; }
    .gift-order-summary { flex-wrap: wrap; }
}

@media (prefers-reduced-motion: reduce) {
    .gift-card, .gift-card * { transition: none !important; }
}
'@

$Files['templates/smsmarket/my_purchases.html'] = @'
{% extends 'base.html' %}
{% load humanize %}
{% load static %}

{% block title %}My Purchases{% endblock %}
{% block page_title %}My Purchases{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/purchases.css' %}?v=3">
{% endblock %}

{% block content %}
<div class="mp-wrap">

    <!-- ===== Header ===== -->
    <div class="mp-head-row">
        <div>
            <h1>My Purchases</h1>
            <p>Every log, number and gift order &mdash; tap any order for full details.</p>
        </div>
        <div class="mp-head-actions">
            <a href="{% url 'marketplace' %}" class="mp-btn mp-btn-solid"><i class="bi bi-shop"></i> Buy Logs</a>
            <a href="{% url 'buynumber' %}" class="mp-btn mp-btn-ghost"><i class="bi bi-phone"></i> Buy Number</a>
            <a href="{% url 'gift_sending' %}" class="mp-btn mp-btn-ghost"><i class="bi bi-gift"></i> Send Gift</a>
        </div>
    </div>

    <!-- ===== Tabs ===== -->
    <div class="mp-tabs" id="mpTabs">
        <button class="mp-tab active" data-type="all">All</button>
        <button class="mp-tab" data-type="log">Logs</button>
        <button class="mp-tab" data-type="number">Numbers</button>
        <button class="mp-tab" data-type="gift">Gifts</button>
    </div>

    <!-- ===== Orders list (newest first, view-sorted) ===== -->
    <div class="mp-card" id="mpList">
        {% for o in orders %}
        <div class="mp-row" data-type="{{ o.type }}"
             data-name="{{ o.name }}"
             data-ref="{{ o.order_id }}"
             data-detail="{{ o.detail }}"
             data-otp="{{ o.otp }}"
             data-format="{{ o.format_labels }}"
             data-price="{{ o.price }}"
             data-date="{{ o.created_at|date:'M j, Y' }} &middot; {{ o.created_at|date:'H:i' }}"
             data-status="{{ o.status }}"
             data-image="{{ o.image }}"
             data-extra="{{ o.extra }}">

            {% if o.image %}
            <img class="mp-thumb" src="{{ o.image }}" alt="{{ o.name }}">
            {% else %}
            <div class="mp-icon {{ o.type }}">
                {% if o.type == 'log' %}<i class="bi bi-file-lock2"></i>
                {% elif o.type == 'number' %}<i class="bi bi-phone"></i>
                {% else %}<i class="bi bi-gift"></i>{% endif %}
            </div>
            {% endif %}

            <div class="mp-main">
                <p class="mp-name">
                    {{ o.name }}{% if o.extra %} &middot; {{ o.extra }}{% endif %}
                    {% if o.order_id %}<span class="mp-ref">{{ o.order_id }}</span>{% endif %}
                </p>
                {% if o.type == 'log' %}
                <p class="mp-sub">
                    <span class="mp-credline">{{ o.detail|truncatechars:55|default:"&mdash;" }}</span>
                    {% if o.detail %}
                    <button class="mp-copychip mp-rowcopy" data-copy="{{ o.detail|escape }}" title="Copy login" type="button">
                        <i class="bi bi-clipboard"></i>
                    </button>
                    {% endif %}
                </p>
                {% elif o.type == 'number' %}
                <p class="mp-sub mono">{{ o.detail|default:"Awaiting number" }}</p>
                {% if o.otp %}
                <p class="mp-sub">
                    <span class="mp-credline">OTP: {{ o.otp }}</span>
                    <button class="mp-copychip mp-rowcopy" data-copy="{{ o.otp }}" title="Copy OTP" type="button">
                        <i class="bi bi-clipboard"></i>
                    </button>
                </p>
                {% endif %}
                {% endif %}
                {% if o.type == 'gift' %}
                <p class="mp-sub">{{ o.detail|truncatechars:70 }}</p>
                {% endif %}
                <p class="mp-date">{{ o.created_at|date:"M j, Y" }} &middot; {{ o.created_at|date:"H:i" }}</p>
            </div>

            <div class="mp-side">
                <span class="mp-price">&#8358;{{ o.price|floatformat:2|intcomma }}</span>
                {% if o.status == 'completed' %}
                <span class="mp-badge completed">Completed</span>
                {% elif o.status == 'active' or o.status == 'waiting' or o.status == 'pending' or o.status == 'processing' or o.status == 'shipped' %}
                <span class="mp-badge {{ o.status }}">{{ o.status|title }}</span>
                {% elif o.status == 'cancelled' or o.status == 'canceled' %}
                <span class="mp-badge cancelled">Cancelled</span>
                {% elif o.status == 'expired' %}
                <span class="mp-badge expired">Expired</span>
                {% else %}
                <span class="mp-badge failed">{{ o.status|title }}</span>
                {% endif %}
            </div>

            <i class="bi bi-chevron-right mp-chev"></i>
        </div>
        {% empty %}
        <div class="mp-empty">
            <i class="bi bi-bag"></i>
            Nothing here yet.
            <div>
                <a href="{% url 'marketplace' %}" class="mp-btn mp-btn-ghost">Buy Logs</a>
                <a href="{% url 'buynumber' %}" class="mp-btn mp-btn-solid">Buy Number</a>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="mp-empty" id="mpNone" hidden>
        <i class="bi bi-funnel"></i>
        Nothing in this category yet.
    </div>

</div>

<!-- ================= ORDER DETAILS CARD ================= -->
<div class="mp-overlay" id="mpModal" hidden>
    <div class="mp-modal" role="dialog" aria-modal="true">

        <!-- product image (logs with image) or type icon -->
        <img class="mpm-img" id="mpmImg" src="" alt="" hidden>
        <div class="mpm-icon" id="mpmIconWrap"><i class="bi bi-file-lock2" id="mpmIcon"></i></div>

        <h5 class="mpm-title" id="mpmTitle"></h5>
        <span class="mpm-ref mono" id="mpmRef" hidden></span>

        <!-- format pill (logs only) -->
        <div id="mpmFormatWrap" hidden>
            <p class="mpm-label">Format</p>
            <div class="mpm-format mono" id="mpmFormat"></div>
        </div>

        <!-- main details box -->
        <p class="mpm-label" id="mpmBoxLabel">Details</p>
        <div class="mpm-box">
            <span class="mpm-box-text mono" id="mpmText"></span>
            <button type="button" class="mpm-copy" id="mpmCopy">
                <i class="bi bi-clipboard"></i><span>Copy</span>
            </button>
        </div>

        <!-- OTP row (numbers only) -->
        <div class="mpm-otp-row" id="mpmOtpRow" hidden>
            <span class="lbl">OTP</span>
            <strong class="mono" id="mpmOtp"></strong>
            <button type="button" class="mpm-copy" id="mpmOtpCopy">
                <i class="bi bi-clipboard"></i>
            </button>
        </div>

        <!-- meta -->
        <div class="mpm-meta">
            <div><em>Price</em><span id="mpmPrice"></span></div>
            <div><em>Date</em><span id="mpmDate"></span></div>
            <span class="mp-badge completed" id="mpmBadge"></span>
        </div>

        <button type="button" class="mpm-done" id="mpmDone">
            <i class="bi bi-check2"></i> Done
        </button>

    </div>
</div>

<div class="mp-toast" id="mpToast" hidden>Copied!</div>

{% endblock %}

{% block extra_js %}
<script>
(function () {
    "use strict";

    /* ---------- TABS ---------- */
    var tabs = document.querySelectorAll("#mpTabs .mp-tab");
    var rows = document.querySelectorAll("#mpList .mp-row");
    var mpNone = document.getElementById("mpNone");

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            tabs.forEach(function (t) { t.classList.remove("active"); });
            tab.classList.add("active");
            var type = tab.getAttribute("data-type");
            var visible = 0;
            rows.forEach(function (row) {
                var show = (type === "all" || row.getAttribute("data-type") === type);
                row.style.display = show ? "" : "none";
                if (show) visible++;
            });
            mpNone.hidden = visible !== 0;
        });
    });

    /* ---------- COPY UTILITY ---------- */
    var toast = document.getElementById("mpToast");
    var toastTimer = null;

    function showToast(msg) {
        toast.textContent = msg || "Copied!";
        toast.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { toast.hidden = true; }, 1600);
    }

    function copyText(text, btn) {
        if (!text) return;
        function done() {
            showToast("Copied to clipboard");
            if (btn) {
                var icon = btn.querySelector("i");
                if (icon) {
                    var old = icon.className;
                    icon.className = "bi bi-check2";
                    setTimeout(function () { icon.className = old; }, 1400);
                }
            }
        }
        function fallback() {
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand("copy"); done(); } catch (e) { showToast("Copy failed"); }
            document.body.removeChild(ta);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, fallback);
        } else { fallback(); }
    }

    /* row-level copy chips (don't open modal) */
    document.querySelectorAll(".mp-rowcopy").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            copyText(btn.getAttribute("data-copy"), btn);
        });
    });

    /* ---------- DETAILS MODAL ---------- */
    var modal = document.getElementById("mpModal");
    var mpmImg = document.getElementById("mpmImg");
    var mpmIconWrap = document.getElementById("mpmIconWrap");

    function openModal(row) {
        var d = function (k) { return row.getAttribute("data-" + k) || ""; };
        var type = d("type");

        /* image takes priority over the generic icon */
        var img = d("image");
        if (img) {
            mpmImg.src = img;
            mpmImg.alt = d("name");
            mpmImg.hidden = false;
            mpmIconWrap.hidden = true;
        } else {
            mpmImg.hidden = true;
            mpmImg.src = "";
            mpmIconWrap.hidden = false;
            document.getElementById("mpmIcon").className =
                type === "log" ? "bi bi-file-lock2" :
                (type === "number" ? "bi bi-phone" : "bi bi-gift");
        }

        document.getElementById("mpmTitle").textContent = d("name");

        var ref = document.getElementById("mpmRef");
        if (d("ref")) { ref.textContent = d("ref"); ref.hidden = false; }
        else { ref.hidden = true; }

        /* format block: logs only */
        var formatWrap = document.getElementById("mpmFormatWrap");
        if (type === "log" && d("format")) {
            document.getElementById("mpmFormat").textContent = d("format");
            formatWrap.hidden = false;
        } else {
            formatWrap.hidden = true;
        }

        document.getElementById("mpmBoxLabel").textContent =
            type === "number" ? "Phone Number" :
            (type === "gift" ? "Recipient & Delivery Details" : "Login Details");
        document.getElementById("mpmText").textContent = d("detail") || "\u2014";

        /* OTP: numbers only */
        var otpRow = document.getElementById("mpmOtpRow");
        if (type === "number" && d("otp")) {
            document.getElementById("mpmOtp").textContent = d("otp");
            otpRow.hidden = false;
        } else {
            otpRow.hidden = true;
        }

        document.getElementById("mpmPrice").textContent =
            "\u20A6" + parseFloat(d("price") || "0").toLocaleString("en-US",
                { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById("mpmDate").textContent = d("date");

        var badge = document.getElementById("mpmBadge");
        var st = d("status");
        badge.textContent = st.charAt(0).toUpperCase() + st.slice(1);
        badge.className = "mp-badge " + st;

        modal.hidden = false;
        document.body.style.overflow = "hidden";
    }

    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = "";
    }

    rows.forEach(function (row) {
        row.addEventListener("click", function (e) {
            if (e.target.closest(".mp-rowcopy")) return;
            openModal(row);
        });
    });

    document.getElementById("mpmDone").addEventListener("click", closeModal);
    modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !modal.hidden) closeModal();
    });

    document.getElementById("mpmCopy").addEventListener("click", function () {
        copyText(document.getElementById("mpmText").textContent, this);
    });
    document.getElementById("mpmOtpCopy").addEventListener("click", function () {
        copyText(document.getElementById("mpmOtp").textContent, this);
    });
})();
</script>
{% endblock %}
'@

$PurchaseCssAddition = @'

/* Gift orders */
.mp-icon.gift { background: #fdf3d8; color: #9a6700; }
.mp-badge.pending, .mp-badge.processing { background: #fef3c7; color: #92400e; }
.mp-badge.shipped { background: #dbeafe; color: #1d4ed8; }
'@

$IntegrationPatch = @'
from pathlib import Path
import re

settings_path = Path("config/settings.py")
settings_text = settings_path.read_text(encoding="utf-8")
installed_gift_apps = (
    '"gifts"', "'gifts'",
    '"gifts.apps.GiftsConfig"', "'gifts.apps.GiftsConfig'",
)
if not any(app in settings_text for app in installed_gift_apps):
    raise SystemExit("Add 'gifts' to INSTALLED_APPS in config/settings.py before running this installer.")

path = Path("smsmarket/views.py")
text = path.read_text(encoding="utf-8")
marker = "# --- Gift orders (managed by the gifts app) ---"

if marker not in text:
    if "from gifts.models import GiftOrder" not in text:
        text = "from gifts.models import GiftOrder\n" + text

    function_match = re.search(r"(?m)^def my_purchases\([^\n]*\):", text)
    if not function_match:
        raise SystemExit("Could not find def my_purchases in smsmarket/views.py")

    next_function = re.search(r"(?m)^def ", text[function_match.end():])
    function_end = function_match.end() + next_function.start() if next_function else len(text)
    function_text = text[function_match.start():function_end]

    if "my_purchases.html" not in function_text:
        raise SystemExit("Could not find the My Purchases render call")

    lines = function_text.splitlines(keepends=True)
    template_index = next(i for i, line in enumerate(lines) if "my_purchases.html" in line)
    return_index = None
    for i in range(template_index, -1, -1):
        if lines[i].lstrip().startswith("return render("):
            return_index = i
            break
    if return_index is None:
        raise SystemExit("Could not locate the return render statement")

    integration = '''    # --- Gift orders (managed by the gifts app) ---
    for gift in GiftOrder.objects.filter(user=request.user):
        recipient_details = "\\n".join([
            gift.recipient_full_name,
            gift.recipient_address,
            f"Postal/ZIP: {gift.recipient_postal_code}",
            gift.recipient_country,
            f"Phone: {gift.recipient_phone}",
        ])
        orders.append({
            "type": "gift",
            "name": gift.product_name,
            "detail": recipient_details,
            "otp": "",
            "price": gift.price,
            "status": gift.status,
            "created_at": gift.created_at,
            "order_id": gift.order_id,
            "format_labels": "",
            "description": gift.customer_note,
            "uid": "",
            "password": "",
            "image": gift.product_image_url,
            "extra": gift.category_name,
        })
    orders.sort(key=lambda item: item["created_at"], reverse=True)

'''
    lines.insert(return_index, integration)
    new_function = "".join(lines)
    text = text[:function_match.start()] + new_function + text[function_end:]
    path.write_text(text, encoding="utf-8")
    print("Gift orders connected to My Purchases.")
else:
    print("My Purchases gift integration already exists.")

urls_path = Path("config/urls.py")
urls = urls_path.read_text(encoding="utf-8")
if "gifts.urls" not in urls:
    if "include" not in urls:
        raise SystemExit("config/urls.py does not import include; add the gifts URL include manually.")
    updated, count = re.subn(
        r"urlpatterns\s*=\s*\[",
        'urlpatterns = [\n    path("", include("gifts.urls")),',
        urls,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not find urlpatterns in config/urls.py")
    urls_path.write_text(updated, encoding="utf-8")
    print("Gift URLs added to config/urls.py.")
else:
    print("Gift URLs are already registered.")

if "SUPPORT_EMAIL" not in settings_text:
    settings_path.write_text(
        settings_text.rstrip() + '\n\n# Gift-order support inbox\nSUPPORT_EMAIL = config("SUPPORT_EMAIL", default="support@pabloexchange.com")\n',
        encoding="utf-8",
    )
    print("SUPPORT_EMAIL setting added.")
'@

foreach ($Entry in $Files.GetEnumerator()) {
    Write-Utf8File -RelativePath $Entry.Key -Content $Entry.Value
}

# Add the gift-specific purchase styles only once.
$PurchaseCssPath = "static/css/purchases.css"
$ExistingPurchaseCss = [System.IO.File]::ReadAllText((Join-Path $ProjectRoot $PurchaseCssPath))
if (-not $ExistingPurchaseCss.Contains(".mp-icon.gift")) {
    $UpdatedPurchaseCss = $ExistingPurchaseCss.TrimEnd() + "`n`n" + $PurchaseCssAddition.Trim() + "`n"
    Write-Utf8File -RelativePath $PurchaseCssPath -Content $UpdatedPurchaseCss
    Write-Host "Gift purchase styles added." -ForegroundColor DarkGray
}
else {
    Write-Host "Gift purchase styles already exist; skipped." -ForegroundColor DarkGray
}

# Back up project files changed by the text-based integration patch.
foreach ($IntegrationFile in @("smsmarket/views.py", "config/urls.py", "config/settings.py")) {
    Backup-File -RelativePath $IntegrationFile
}

$PatchScript = Join-Path $ProjectRoot ".gift_installer_patch.py"
try {
    [System.IO.File]::WriteAllText(
        $PatchScript,
        $IntegrationPatch,
        (New-Object System.Text.UTF8Encoding($false))
    )
    Write-Host "`nConnecting gift orders, URLs, and support email..." -ForegroundColor Cyan
    & python $PatchScript
    if ($LASTEXITCODE -ne 0) {
        throw "The project integration patch failed. Review the message above; backups are at $BackupRoot"
    }
}
finally {
    if (Test-Path -LiteralPath $PatchScript) {
        Remove-Item -LiteralPath $PatchScript -Force
    }
}

Invoke-Django -Arguments @("manage.py", "check")
Invoke-Django -Arguments @("manage.py", "makemigrations", "gifts")
Invoke-Django -Arguments @("manage.py", "migrate")

Write-Host "`nGift Sending installation completed successfully." -ForegroundColor Green
Write-Host "Backups of replaced files: $BackupRoot" -ForegroundColor DarkGray
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Open Django admin > Gifts and add Gift Categories and Gift Products."
Write-Host "2. Add category/product images and set each product price in naira."
Write-Host "3. Set SUPPORT_EMAIL in your local .env and Render environment to the inbox that receives orders."
Write-Host "4. Test a small order, then check My Purchases and Django admin > Gift orders."
Write-Host "5. Keep .env and all credentials out of GitHub."
