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
            return format_html(
                '<span style="color:#047857;font-weight:700;">{}</span>',
                "Completed",
            )
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
            "title": f"Confirm completion \u2014 {order.order_id}",
            "opts": self.model._meta,
            "order": order,
            "can_complete": order.can_mark_completed(),
        }
        return render(
            request,
            "admin/gifts/giftorder/confirm_completed.html",
            context,
        )