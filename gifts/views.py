
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from wallet.services import balance as get_balance

from .forms import GiftOrderForm
from .models import GiftCategory, GiftProduct
from .services import GiftOrderError, create_gift_order


@login_required
def gift_sending(request):
    products = GiftProduct.objects.filter(is_active=True).select_related("category")
    categories = (
        GiftCategory.objects.filter(is_active=True, products__is_active=True)
        .distinct()
        .prefetch_related(Prefetch("products", queryset=products))
    )
    return render(request, "gifts/gift_sending.html", {
        "categories": categories,
        "balance": get_balance(request.user),
    })


@login_required
@require_POST
def gift_order_create(request, product_id):
    form = GiftOrderForm(request.POST)
    if not form.is_valid():
        errors = {
            field: [item["message"] for item in messages]
            for field, messages in form.errors.get_json_data().items()
        }
        return JsonResponse({
            "success": False,
            "error": "Please correct the highlighted recipient details.",
            "errors": errors,
        }, status=400)

    try:
        order = create_gift_order(
            user=request.user,
            product_id=product_id,
            recipient_data=form.cleaned_data,
            images=request.FILES.getlist("images"),
        )
    except GiftOrderError as exc:
        payload = {"success": False, "error": str(exc)}
        if getattr(exc, "field", None):
            payload["errors"] = {exc.field: [str(exc)]}
        return JsonResponse(payload, status=400)

    return JsonResponse({
        "success": True,
        "order_id": order.order_id,
        "product_name": order.product_name,
        "status": order.status,
        "new_balance": str(get_balance(request.user)),
        "message": "Your gift order has been placed and is now pending.",
    })
