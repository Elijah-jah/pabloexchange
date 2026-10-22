from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('buynumber/', RedirectView.as_view(pattern_name='smsmarket:buy', permanent=True), name='buynumber'),
    path('marketplace/', views.marketplace_logs, name='marketplace'),
    path('marketplace/logs/buy/<int:pk>/', views.purchase_log, name='purchase_log'),
    path('marketplace/logs/deliver/<int:pk>/', views.deliver_log, name='deliver_log'),
]