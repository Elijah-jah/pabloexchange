from django.contrib import admin
from django.utils.html import format_html

from .models import Pricing, PricingConfiguration


def status_badge(active):
    if active:
        return format_html('<span style="color:#059669;font-weight:700;">{}</span>', 'Active')
    return format_html('<span style="color:#dc2626;font-weight:700;">{}</span>', 'Inactive')


@admin.register(PricingConfiguration)
class PricingConfigurationAdmin(admin.ModelAdmin):
    list_display = ('exchange_rate', 'fixed_profit', 'updated_at')

    def has_add_permission(self, request):
        return not PricingConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class ServiceStatusFilter(admin.SimpleListFilter):
    title = 'status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [('active', 'Active'), ('inactive', 'Inactive')]

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(service__is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(service__is_active=False)
        return queryset


@admin.register(Pricing)
class PricingAdmin(admin.ModelAdmin):
    list_display = ('country', 'service', 'provider_cost', 'profit',
                    'sell_price', 'is_available', 'status')
    list_filter = ('country', ServiceStatusFilter, 'is_available')
    search_fields = ('service__name', 'service__code', 'country__name', 'country__code')
    list_editable = ('sell_price', 'is_available')
    list_display_links = ('service',)
    list_per_page = 100
    ordering = ('country__name', 'service__name')
    readonly_fields = ('updated_at',)

    @admin.display(description='Provider cost')
    def provider_cost(self, obj):
        if obj.cost_usd > 0:
            return f'${obj.cost_usd}'
        return format_html('<span style="color:#dc2626;">{}</span>', '—')

    @admin.display(description='Profit (₦)')
    def profit(self, obj):
        config = PricingConfiguration.objects.first()
        fx = config.exchange_rate if config else 1650   
        p = obj.sell_price - (obj.cost_usd * fx)
        return f'₦{p:,.2f}'

    @admin.display(description='Status')
    def status(self, obj):
        return status_badge(obj.service.is_active and obj.country.is_active)