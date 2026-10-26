import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .providers import get_provider
from countries.models import Country
from marketplace.models import LogOrder
from pricing.models import Pricing
from wallet.services import get_wallet

from .models import NumberOrder, Service
from .services import (InsufficientFunds, PricingNotAvailable,
                       cancel_user_order, maybe_deliver, reserve_number)

logger = logging.getLogger(__name__)


@login_required
def for_country(request, code):
    """JSON: services for one country. DB rows include their prices; live
    catalog items return price=None and are priced on demand when selected."""
    country = get_object_or_404(Country, code=code, is_active=True)
    server = request.GET.get('server', 'instantnums')
    if server not in ('daisysms', 'instantnums'):
        server = 'instantnums'

    rows = (
        Pricing.objects
        .filter(country=country, is_available=True, service__is_active=True)
        .select_related('service')
        .order_by('service__name')
    )

    seen = set()
    seen_names = set()
    services = []
    for row in rows:
        seen.add(row.service.code)
        seen_names.add(row.service.name.lower())
        services.append({
            'code': row.service.code,
            'name': row.service.name,
            'price': str(row.sell_price),
        })

    from .services import live_catalog
    for item in live_catalog(server, country.code, exclude_codes=seen):
        if item['name'].lower() in seen_names:
            continue
        services.append(item)

    services.sort(key=lambda s: s['name'])
    return JsonResponse({'services': services})


@login_required
def check_price(request):
    """JSON: live sell price for one service+country. Fetched by buynumber.js
    when the customer selects a service that came from the live catalog."""
    service = (request.GET.get('service') or '').strip()
    country = (request.GET.get('country') or '').strip()
    server = request.GET.get('server', 'instantnums')
    if server not in ('daisysms', 'instantnums'):
        server = 'instantnums'
    if not service or not country:
        return JsonResponse({'error': 'missing parameters'}, status=400)

    from .services import live_sell_price
    sell = live_sell_price(server, service, country)
    if sell is None:
        return JsonResponse({'available': False})
    return JsonResponse({'available': True, 'price': str(sell)})


@login_required
def buy(request):
    wallet = get_wallet(request.user)

    # --- AJAX support: works whether fetch() sends the header or a flag ---
    ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.POST.get("ajax") == "1"
    )

    def ajax_error_response(redirect_to="smsmarket:buy"):
        try:
            target = reverse(redirect_to)
        except NoReverseMatch:
            logger.exception('Could not reverse %r; falling back to buy page', redirect_to)
            target = reverse("smsmarket:buy")
        if ajax:
            msg_text, msg_level = "", "error"
            for m in messages.get_messages(request):
                msg_text = str(m)
                msg_level = m.level_tag
            return JsonResponse({
                "success": False,
                "message": msg_text,
                "level": msg_level,
                "redirect": target,
            })
        return redirect(target)

    if request.method == 'POST':
        service_code = (request.POST.get('service') or '').strip()
        country_code = (request.POST.get('country') or '').strip()
        server = request.POST.get('server', 'instantnums')
        if server not in ('daisysms', 'instantnums'):
            server = 'instantnums'

        # Validate country BEFORE reserve_number — stale/unknown codes
        # redirect with a message, never a 500.
        try:
            Country.objects.get(code__iexact=country_code, is_active=True)
        except Country.DoesNotExist:
            logger.warning(
                'Buy rejected: country code %r (server=%s) not found or inactive for user %s',
                country_code, server, request.user.id,
            )
            messages.error(request,
                           'That country is no longer available. '
                           'Please refresh and pick another.')
            return ajax_error_response('smsmarket:buy')

        try:
            order = reserve_number(request.user, service_code=service_code,
                                   country_code=country_code, provider_name=server)
        except PricingNotAvailable as e:
            logger.warning('Buy rejected: %s (user=%s, country=%s, service=%s, server=%s)',
                           e, request.user.id, country_code, service_code, server)
            messages.error(request, str(e))
            return ajax_error_response('smsmarket:buy')
        except InsufficientFunds as e:
            messages.error(request, str(e))
            return ajax_error_response('wallet:deposit')
        except Exception as e:
            logger.exception('reserve_number failed for user %s: %s',
                             request.user.id, e)
            messages.error(request,
                           'Unable to complete your request. Please try again shortly.')
            return ajax_error_response('smsmarket:buy')

        # --- AJAX success: return the order as JSON, page stays put ---
        if ajax:
            return JsonResponse({
                'success': True,
                'message': 'Number reserved. You are only charged when the SMS arrives.',
                'order': {
                    'id': order.id,
                    'phone_number': order.phone_number,
                    'price': str(order.price),
                    'status': order.status,
                    'created_at': order.created_at.isoformat(),
                },
            })

        messages.success(request,
                         'Number reserved. You are only charged when the SMS arrives.')
        return redirect('smsmarket:buy')

    # GET: render the buy page
    countries = Country.objects.filter(is_active=True)

    # Cards live until the timer runs out — NOT just until the SMS lands.
    #   • status='active'  → still waiting for the code
    #   • has messages     → code already delivered; card stays until expiry
    # Orders past expires_at (timer hit 00:00) or cancelled are excluded,
    # so the card disappears exactly when the timer ends.
    now = timezone.now()
    active_orders = (
        NumberOrder.objects
        .filter(user=request.user, expires_at__gt=now)
        .exclude(status='cancelled')
        .filter(Q(status='active') | Q(messages__isnull=False))
        .distinct()
        .order_by('expires_at')
    )

    return render(request, 'smsmarket/buynumber.html', {
        'countries': countries,
        'active_orders': active_orders,
        'balance': wallet.balance,
    })


@login_required
def order_status(request, pk):
    """JSON: current status + OTP for an order. Powers silent page polling."""
    order = get_object_or_404(NumberOrder, pk=pk, user=request.user)
    maybe_deliver(order)
    order.refresh_from_db()
    msg = order.messages.last()
    return JsonResponse({
        'status': order.status,
        'otp': msg.otp_code if msg else '',
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

    if order.status != 'active':
        messages.info(request, 'This order is no longer active.')
        return redirect('smsmarket:buy')

    # Cancel with the provider FIRST. If the provider says it can't be
    # cancelled, say so — don't pretend it worked. Nothing was ever charged.
    if order.provider_order_id:
        try:
            get_provider(order.provider).cancel(order.provider_order_id)
        except Exception as e:
            reason = str(e)[:120]
            logger.warning('Provider cancel refused for order %s (%s): %s',
                           order.id, order.provider, e)
            messages.error(
                request,
                "This order can't be cancelled — the provider refused "
                f'({reason}). It may have already expired. No charge was made.'
            )
            return redirect('smsmarket:buy')

    order.status = 'cancelled'
    order.save(update_fields=['status'])
    messages.success(request, 'Order cancelled — you were not charged.')
    return redirect('smsmarket:buy')


@login_required
def my_purchases(request):
    """All purchases — logs and numbers merged, newest first."""
    numbers = (NumberOrder.objects
               .filter(user=request.user)
               .select_related('service', 'country'))
    logs = (LogOrder.objects
            .filter(user=request.user)
            .select_related('group'))

    orders = []

    # ---- SMS number purchases ----
    for o in numbers:
        otp_msg = o.messages.last()
        orders.append({
            'type': 'number',
            'name': o.service.name if o.service else 'Number',
            'order_id': '',
            'detail': o.phone_number or '',
            'otp': otp_msg.otp_code if otp_msg else '',
            'format_labels': '',
            'price': o.price,
            'status': o.status,
            'created_at': o.created_at,
            'image': '',
            'extra': o.country.name if o.country else '',
        })

    # ---- Log purchases ----
    for o in logs:
        orders.append({
            'type': 'log',
            'name': o.group_name,
            'order_id': o.order_id,          # PLOG####
            'detail': o.credentials or '',
            'otp': '',
            'format_labels': (o.group.format_labels if o.group
                               else 'UID | PASSWORD | EMAIL PASSWORD | 2FA | RECOVERY EMAIL'),
            'price': o.price,
            'status': o.status,
            'created_at': o.created_at,
            'image': o.group.image.url if (o.group and o.group.image) else '',
            'extra': '',
        })

    # newest purchase first across both types
    orders.sort(key=lambda x: x['created_at'], reverse=True)

    return render(request, 'smsmarket/my_purchases.html', {
        'orders': orders,
    })