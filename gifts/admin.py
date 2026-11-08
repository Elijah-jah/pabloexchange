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
        return "â€”"


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
        return "â€”"


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