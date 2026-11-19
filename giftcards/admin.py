from django.contrib import admin
from django.utils.html import format_html

from .models import GiftCard, GiftCardCategory, GiftCardCountry, GiftCardOrder


@admin.register(GiftCardCountry)
class GiftCardCountryAdmin(admin.ModelAdmin):
    list_display = ("name", "flag_emoji", "display_order", "is_active")
    list_editable = ("flag_emoji", "display_order", "is_active")
    search_fields = ("name",)


@admin.register(GiftCardCategory)
class GiftCardCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("name",)


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview", "name", "category", "country",
        "min_amount_usd", "max_amount_usd",
        "display_order", "is_active", "created_at",
    )
    list_filter = ("category", "country", "is_active")
    list_editable = (
        "min_amount_usd", "max_amount_usd", "display_order", "is_active",
    )
    search_fields = ("name", "description", "category__name", "country__name")

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:44px;height:44px;object-fit:cover;border-radius:8px;">',
                obj.image.url,
            )
        return "\u2014"


@admin.register(GiftCardOrder)
class GiftCardOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id", "card_name", "user", "buyer_name",
        "amount_usd", "quantity", "total_ngn", "status", "created_at",
    )
    list_select_related = ("user",)
    list_filter = ("status", "category_name", "country_name", "created_at")
    list_editable = ("status",)
    search_fields = (
        "order_id", "card_name", "buyer_name",
        "user__username", "user__email",
    )
    readonly_fields = (
        "order_id", "user", "card", "card_name", "category_name",
        "country_name", "buyer_name", "amount_usd", "quantity",
        "exchange_rate", "total_ngn", "created_at", "updated_at",
    )
