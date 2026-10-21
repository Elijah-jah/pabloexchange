from django.urls import path

from smsmarket import views as smsmarket_views

urlpatterns = [
    path('for-country/<str:code>/', smsmarket_views.for_country, name='for_country'),
    path('check-price/', smsmarket_views.check_price, name='check_price'),
]