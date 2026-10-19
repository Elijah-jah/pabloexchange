from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from smsmarket.models import Service

from .models import Pricing


@login_required
def services_for_country(request, code):
    """Services for a country on a given server, each with 'available' flag.
    ?server=daisysms (Server 1, USA) or ?server=instantnums (Server 2, all countries)."""
    provider = request.GET.get('server', 'instantnums')
    if provider not in ('daisysms', 'instantnums'):
        provider = 'instantnums'

    priced = {
        p.service_id: p
        for p in Pricing.objects.filter(provider=provider,
                                        country__code=code.upper()).select_related('service')
    }

    services = []
    for svc in Service.objects.filter(provider=provider, is_active=True):
        p = priced.get(svc.id)
        available = bool(p and p.is_available and p.sell_price > 0)
        services.append({
            'code': svc.code,
            'name': svc.name,
            'available': available,
            'price': str(p.sell_price) if available else None,
        })

    return JsonResponse({'services': services})