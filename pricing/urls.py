from django.urls import path

from . import views

urlpatterns = [
    path('for-country/<str:code>/', views.services_for_country, name='services_for_country'),
]