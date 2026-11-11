from gifts.models import GiftOrder
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from smsmarket.models import NumberOrder, Service
from wallet.models import WalletTransaction
from wallet.services import balance


def home(request):
    return render(request, 'pages/home.html', {
        'services': Service.objects.filter(is_active=True)[:12],
    })


from marketplace.models import LogOrder

@login_required
def dashboard(request):
    show_login_notice = request.session.pop('show_login_notice', False)

    all_orders = NumberOrder.objects.filter(user=request.user)
    all_logs = LogOrder.objects.filter(user=request.user)
    # --- Dashboard gift-order tracking ---
    gift_order_queryset = GiftOrder.objects.filter(user=request.user)
    gift_order_count = gift_order_queryset.count()
    gift_completed_count = gift_order_queryset.filter(status="completed").count()
    gift_active_count = gift_order_queryset.filter(
        status__in=["pending", "processing", "shipped"]
    ).count()
    gift_orders = gift_order_queryset[:5]

    # Existing dashboard totals now include gifts as well as numbers/logs.
    order_count = locals().get("order_count", 0) + gift_order_count
    completed_count = locals().get("completed_count", 0) + gift_completed_count
    active_count = locals().get("active_count", 0) + gift_active_count

    return render(request, 'pages/dashboard.html', {
        "show_login_notice": show_login_notice,
        "gift_order_count": gift_order_count,
        "gift_active_count": gift_active_count,
        "gift_completed_count": gift_completed_count,
        "gift_orders": gift_orders,
        'balance': balance(request.user),
        'orders': all_orders[:5],
        'transactions': WalletTransaction.objects.filter(user=request.user)[:5],
        # stats for the cards — logs + SMS combined
        'order_count': all_orders.count() + all_logs.count(),
        'completed_count': (
            all_orders.filter(status='completed').count() +
            all_logs.filter(status='completed').count()
        ),
        'active_count': all_orders.filter(status='active').count(),  # SMS only
    })