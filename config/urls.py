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