from django.contrib import admin

# Register your models here.



# ---------------------------------------------------------------------------
# Site settings - a single editable record (site name + logo)
# ---------------------------------------------------------------------------
from django.shortcuts import redirect as _redirect
from django.utils.html import format_html as _format_html

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("site_name", "logo_preview", "updated_at")
    readonly_fields = ("logo_preview", "updated_at")
    fields = ("site_name", "logo", "logo_preview", "updated_at")

    @admin.display(description="Current logo")
    def logo_preview(self, obj):
        if obj and obj.logo:
            return _format_html(
                '<img src="{}" alt="" style="height:48px;max-width:220px;border-radius:8px;background:#fff;padding:4px;">',
                obj.logo.url,
            )
        return "No logo uploaded yet"

    def has_add_permission(self, request):
        # Only one Site settings record may ever exist.
        return not SiteSettings.objects.exists()

    def changelist_view(self, request, extra_context=None):
        # Jump straight into the single record instead of showing a list.
        obj = SiteSettings.objects.first()
        if obj is not None:
            return _redirect("admin:pages_sitesettings_change", obj.pk)
        return super().changelist_view(request, extra_context)
