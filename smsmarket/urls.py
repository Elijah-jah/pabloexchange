from django.urls import path

from . import views

app_name = 'smsmarket'

urlpatterns = [
    path('buy/', views.buy, name='buy'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/cancel/', views.cancel_order, name='cancel_order'),
    path('purchases/', views.my_purchases, name='my_purchases'),
    path("pricing/for-country/<str:code>/", views.for_country, name="pricing_for_country"),
]