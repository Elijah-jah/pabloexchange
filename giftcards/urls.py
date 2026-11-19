from django.urls import path

from . import views


urlpatterns = [
    path("gift-cards/", views.giftcard_store, name="gift_cards"),
    path("gift-cards/<int:pk>/", views.giftcard_detail, name="giftcard_detail"),
    path(
        "gift-cards/<int:pk>/purchase/",
        views.giftcard_purchase,
        name="giftcard_purchase",
    ),
]
