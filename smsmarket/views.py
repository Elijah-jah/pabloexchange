import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

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
    wallet = get_wallet(request.user)

    # --- AJAX support: works whether fetch() sends the header or a flag ---
    ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.POST.get("ajax") == "1"
    )

    def ajax_error_response(redirect_to="smsmarket:buy"):
        if ajax:
            msg_text, msg_level = "", "error"
            for m in messages.get_messages(request):
                msg_text = str(m)
                msg_level = m.level_tag
            return JsonResponse({
                "success": False,
                "message": msg_text,
                "level": msg_level,
                "redirect": reverse(redirect_to),
            })
        return redirect(redirect_to)

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
    active_orders = NumberOrder.objects.filter(user=request.user, status='active')
    return render(request, 'smsmarket/buynumber.html', {
        'countries': countries,
        'active_orders': active_orders,
        'balance': wallet.balance,
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
    """All purchases — logs and numbers merged, newest first."""
    numbers = (NumberOrder.objects
               .filter(user=request.user)
               .select_related('service'))
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
        })

    # newest purchase first across both types
    orders.sort(key=lambda x: x['created_at'], reverse=True)

    return render(request, 'smsmarket/my_purchases.html', {
        'orders': orders,
    })