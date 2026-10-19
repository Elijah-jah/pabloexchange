from django.urls import path

from . import views

urlpatterns = [
    path('buynumber/', views.marketplace, name='buynumber'),
    path('marketplace/', views.marketplace_logs, name='marketplace'),
    path('marketplace/logs/buy/<int:pk>/', views.purchase_log, name='purchase_log'),
    path('marketplace/logs/deliver/<int:pk>/', views.deliver_log, name='deliver_log'),
    path('marketplace/logs/cancel/<int:pk>/', views.cancel_log_order, name='cancel_log_order'),
]