from django.urls import path

from . import views

urlpatterns = [
    path('buynumber/', views.marketplace, name='buynumber'),
    path('marketplace/', views.marketplace_logs, name='marketplace'),
    path('marketplace/purchase/<int:pk>/', views.purchase_log, name='purchase_log'),
]