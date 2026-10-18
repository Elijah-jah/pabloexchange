from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from smsmarket.models import NumberOrder, Service
from wallet.models import WalletTransaction
from wallet.services import balance


def home(request):
    return render(request, 'pages/home.html', {
        'services': Service.objects.filter(is_active=True)[:12],
    })


@login_required
def dashboard(request):
    all_orders = NumberOrder.objects.filter(user=request.user)
    return render(request, 'pages/dashboard.html', {
        'balance': balance(request.user),
        'orders': all_orders[:5],
        'transactions': WalletTransaction.objects.filter(user=request.user)[:5],
        # stats for the cards
        'order_count': all_orders.count(),
        'completed_count': all_orders.filter(status='completed').count(),
        'active_count': all_orders.filter(status='active').count(),
    })