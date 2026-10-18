from django.contrib import admin

from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('updated_at',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'amount', 'status', 'method', 'description', 'created_at')
    list_filter = ('type', 'status', 'method')
    search_fields = ('user__email', 'reference', 'description')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'