from django.urls import path

from . import views

urlpatterns = [
    path('buynumber/', views.marketplace, name='buynumber'),
]



