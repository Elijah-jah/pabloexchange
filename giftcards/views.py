from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from wallet.services import balance as get_balance

from .models import GiftCard, GiftCardCategory, GiftCardCountry
from .services import (
    GiftCardOrderError,
    build_whatsapp_url,
    create_giftcard_order,
    get_exchange_rate,
)


@login_required
def giftcard_store(request):
    cards = (
        GiftCard.objects.filter(
            is_active=True,
            category__is_active=True,
            country__is_active=True,
        )
        .select_related("category", "country")
    )
    # Only show filters that actually have purchasable cards.
    categories = (
        GiftCardCategory.objects.filter(
            is_active=True, cards__is_active=True, cards__country__is_active=True,
        )
        .distinct()
    )
    countries = (
        GiftCardCountry.objects.filter(
            is_active=True, cards__is_active=True, cards__category__is_active=True,
        )
        .distinct()
    )
    return render(request, "giftcards/giftcards.html", {
        "cards": cards,
        "categories": categories,
        "countries": countries,
        "balance": get_balance(request.user),
        "exchange_rate": get_exchange_rate(),
    })


@login_required
def giftcard_detail(request, pk):
    card = get_object_or_404(
        GiftCard.objects.select_related("category", "country"),
        pk=pk,
        is_active=True,
        category__is_active=True,
        country__is_active=True,
    )
    return render(request, "giftcards/giftcard_detail.html", {
        "card": card,
        "balance": get_balance(request.user),
        "exchange_rate": get_exchange_rate(),
    })


@login_required
@require_POST
def giftcard_purchase(request, pk):
    try:
        order = create_giftcard_order(
            user=request.user,
            card_id=pk,
            amount_usd=request.POST.get("amount_usd"),
            quantity=request.POST.get("quantity"),
            buyer_name=request.POST.get("buyer_name"),
        )
    except GiftCardOrderError as exc:
        payload = {"success": False, "error": str(exc)}
        if getattr(exc, "field", None):
            payload["errors"] = {exc.field: [str(exc)]}
        return JsonResponse(payload, status=400)

    return JsonResponse({
        "success": True,
        "order_id": order.order_id,
        "card_name": order.card_name,
        "buyer_name": order.buyer_name,
        "amount_usd": str(order.amount_usd),
        "quantity": order.quantity,
        "total_ngn": str(order.total_ngn),
        "status": order.status,
        "new_balance": str(get_balance(request.user)),
        "whatsapp_url": build_whatsapp_url(order),
    })
