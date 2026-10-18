from django.urls import path

from . import views

urlpatterns = [
    path('buynumber/', views.marketplace, name='buynumber'),
    path('pricing/for-country/<str:code>/', views.for_country, name='pricing_for_country'),
]



