from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pages.urls')),
    path('', include('accounts.urls')),
    path('', include('wallet.urls')),
    path('', include('smsmarket.urls')),
    path('', include('marketplace.urls')),
    path('pricing/', include('pricing.urls')),
]

# Serve uploaded product images locally in development only.
# (On Render production, we'll wire up real media storage later.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)