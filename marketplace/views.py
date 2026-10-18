from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from countries.models import Country
from smsmarket.models import NumberOrder
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from pricing.models import Pricing


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

    # Matches your JS exactly: { services: [{code, name, price}] }
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
def marketplace(request):
    return render(request, 'marketplace/buynumber.html', {
        # ALL active countries — your JS already handles "no services" gracefully
        'countries': Country.objects.filter(is_active=True).order_by('name'),
        'active_orders': NumberOrder.objects.filter(
            user=request.user, status='active'),
        # balance pill in your header reads this — adapt to your wallet relation
        'balance': request.user.wallet.balance,
    })