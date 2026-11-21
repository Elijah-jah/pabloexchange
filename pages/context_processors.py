"""Template context processors for the pages app."""

from .models import SiteSettings


def site_settings(request):
    """Expose the Site settings record to every template as `site_settings`.

    Wrapped in try/except so the site keeps working even before the
    migration for the new table has been applied.
    """
    try:
        return {"site_settings": SiteSettings.objects.first()}
    except Exception:
        return {"site_settings": None}
