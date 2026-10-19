from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from countries.models import Country
from .models import NumberOrder, Service
from .services import (InsufficientFunds, PricingNotAvailable,
                       cancel_user_order, maybe_deliver, reserve_number)


from django.http import JsonResponse
from pricing.models import Pricing   # confirm this import matches your project


@login_required
def for_country(request, code):
    """JSON: services + prices for one country. Feeds buynumber.js."""
    country = get_object_or_404(Country, code=code, is_active=True)

    rows = (
        Pricing.objects
        .filter(country=country, is_available=True, service__is_active=True)
        .select_related('service')
        .order_by('service__name')
    )

    return JsonResponse({
        'services': [
            {
                'code': row.service.code,
                'name': row.service.name,
                'price': str(row.sell_price),
            }
            for row in rows
        ],
    })


@login_required
def buy(request):
    if request.method == 'POST':
        service_code = request.POST.get('service')
        country_code = request.POST.get('country')
        server = request.POST.get('server', 'instantnums')
        if server not in ('daisysms', 'instantnums'):
            server = 'instantnums'
        try:
            order = reserve_number(request.user, service_code=service_code,
                                   country_code=country_code, provider_name=server)
        except PricingNotAvailable as e:
            messages.error(request, str(e))
            return redirect('smsmarket:buy')
        except InsufficientFunds as e:
            messages.error(request, str(e))
            return redirect('wallet:deposit')   # or wherever your funding page is
        return redirect('smsmarket:buy')        # the active orders section shows it
    # GET: render the buy page
    countries = Country.objects.filter(is_active=True)
    active_orders = NumberOrder.objects.filter(user=request.user, status='active')
    return render(request, 'smsmarket/buy_number.html', {
        'countries': countries,
        'active_orders': active_orders,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(NumberOrder, pk=pk, user=request.user)
    maybe_deliver(order)   # poll: delivers OTP if due, charges wallet once
    order.refresh_from_db()
    return render(request, 'smsmarket/order_detail.html', {
        'order': order,
        'received': order.messages.all(),
    })


@login_required
@require_POST
def cancel_order(request):
    order = get_object_or_404(NumberOrder, pk=request.POST.get('order_id'),
                              user=request.user)
    if cancel_user_order(order):
        messages.success(request, 'Order cancelled — you were not charged.')
    else:
        messages.info(request, 'Order could not be cancelled.')
    return redirect('marketplace')


@login_required
def my_purchases(request):
    return render(request, 'smsmarket/my_purchases.html', {
        'orders': NumberOrder.objects.filter(user=request.user),
    })