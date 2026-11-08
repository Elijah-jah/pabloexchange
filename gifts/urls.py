from django.urls import path

from . import views


urlpatterns = [
    path("gifts/", views.gift_sending, name="gift_sending"),
    path(
        "gifts/order/<int:product_id>/",
        views.gift_order_create,
        name="gift_order_create",
    ),
]