from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from smsmarket.models import Service

from .models import Pricing


@login_required
def services_for_country(request, code):
    """All active services for a country, each with an 'available' flag.
    Unavailable ones are rendered disabled in the Buy Number UI."""
    priced = {
        p.service_id: p
        for p in Pricing.objects.filter(country__code=code.upper()).select_related('service')
    }

    services = []
    for svc in Service.objects.filter(is_active=True):
        p = priced.get(svc.id)
        available = bool(p and p.is_available and p.sell_price > 0)
        services.append({
            'code': svc.code,
            'name': svc.name,
            'available': available,
            'price': str(p.sell_price) if available else None,
        })

    return JsonResponse({'services': services})