from django.contrib import admin

from .models import NumberOrder, Service, SmsMessage


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'price', 'price_usd', 'is_active')
    search_fields = ('name', 'code')
    list_editable = ('price', 'is_active')


@admin.register(NumberOrder)
class NumberOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'service', 'country', 'phone_number',
                    'status', 'price', 'created_at')
    list_filter = ('status', 'service', 'country')
    search_fields = ('user__email', 'phone_number', 'provider_order_id')
    readonly_fields = ('reserved_at', 'created_at')
    date_hierarchy = 'created_at'


@admin.register(SmsMessage)
class SmsMessageAdmin(admin.ModelAdmin):
    list_display = ('order', 'sender', 'otp_code', 'received_at')
    search_fields = ('otp_code', 'text', 'order__phone_number')
    readonly_fields = ('received_at',)