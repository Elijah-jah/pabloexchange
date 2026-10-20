import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from countries.models import Country
from smsmarket.models import NumberOrder
from pricing.models import Pricing
from wallet.services import balance as get_balance, can_afford, debit

from .models import LogCategory, LogGroup, LogItem, LogOrder, LogSubCategory

logger = logging.getLogger(__name__)


@login_required
def marketplace_logs(request):
    """Account Logs Shop - sections grouped by subcategory, cards = groups."""
    categories = LogCategory.objects.filter(is_active=True)

    subs = (LogSubCategory.objects
            .filter(is_active=True, category__is_active=True,
                    groups__is_active=True)
            .distinct()
            .order_by('order', 'name')
            .prefetch_related('category'))

    sections = []
    for sub in subs:
        groups = (LogGroup.objects
                  .filter(subcategory=sub, is_active=True)
                  .annotate(_actual_stock=Count('items', filter=Q(items__is_sold=False)))
                  .order_by('name'))
        products = [{
            'id': g.id,
            'title': g.name,
            'price': g.price,
            'stock': max(g._actual_stock, g.stock),
            'description': g.description,
            'image': g.image,
            'format_labels': g.format_labels,
            'category_id': sub.category_id,
        } for g in groups]
        if products:
            sections.append({
                'key': f'sub-{sub.id}',
                'name': sub.name,
                'products': products,
            })

    return render(request, 'marketplace/logs.html', {
        'categories': categories,
        'sections': sections,
        'user_wallet': getattr(request.user, 'wallet', None),
    })


def _deliver_order(order):
    """Attempt to deliver a waiting order: pop creds, debit wallet, complete.

    Returns (ok, error_message). On any failure the order is cancelled and
    NOTHING was charged - credentials stay in stock. Must be called inside
    an atomic block with the order row locked."""
    group = order.group
    if group is None:
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        return False, 'This product is no longer available.'

    item = (LogItem.objects
            .select_for_update()
            .filter(group=group, is_sold=False)
            .order_by('id')
            .first())
    if item is None:
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        group.stock = 0
        group.is_active = False
        group.save(update_fields=['stock', 'is_active'])
        return False, 'Item is sold out.'

    if not can_afford(order.user, order.price):
        balance = getattr(getattr(order.user, 'wallet', None), 'balance', 0) or 0
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        return False, (f'Insufficient funds. This order costs \u20A6{order.price:,.2f} '
                       f'but your balance is \u20A6{balance:,.2f}.')

    # Debit only now - creds are guaranteed in hand.
    # wallet.services.debit() already writes the WalletTransaction ledger
    # row atomically - no explicit audit needed (unlike abfverify's wallet).
    debit(order.user, order.price,
          description=f'Purchase of {group.name} ({order.order_id})',
          meta={'group_id': group.id, 'order_id': order.id})

    item.is_sold = True
    item.sold_at = timezone.now()
    item.save(update_fields=['is_sold', 'sold_at'])

    group.stock = max(0, group.stock - 1)
    if group.stock == 0:
        group.is_active = False
    group.save(update_fields=['stock', 'is_active'])

    order.item = item                    # DB-enforced: one item, one sale
    order.credentials = item.content
    order.status = 'completed'
    order.save(update_fields=['item', 'credentials', 'status'])

    logger.info('Log order %s delivered (user %s, group %s)',
                order.order_id, order.user_id, group.id)
    return True, get_balance(order.user)


@login_required
@require_POST
@transaction.atomic
def purchase_log(request, pk):
    """Reserve + deliver in one request.

    Creates a waiting order, then attempts immediate delivery inside the
    same atomic transaction. Returns the credentials right away when delivery
    succeeds; on failure the order is cancelled, nothing is charged, and
    the customer sees the exact reason."""
    group = get_object_or_404(
        LogGroup.objects.select_for_update().select_related('subcategory'),
        pk=pk, is_active=True,
    )

    real_stock = group.items.filter(is_sold=False).count()
    if group.stock != real_stock:
        group.stock = real_stock
        group.save(update_fields=['stock'])

    if real_stock <= 0:
        return JsonResponse({'success': False, 'error': 'Item is sold out.'}, status=400)

    # Balance must cover this price PLUS everything already reserved
    pending = (LogOrder.objects
               .filter(user=request.user, status='waiting')
               .aggregate(total=Sum('price'))['total'] or 0)
    if not can_afford(request.user, pending + group.price):
        balance = getattr(getattr(request.user, 'wallet', None), 'balance', 0) or 0
        return JsonResponse({'success': False,
                             'error': ('Insufficient funds. You need \u20A6'
                                       f'{pending + group.price:,.2f} (including reserved orders) '
                                       f'but your balance is \u20A6{balance:,.2f}.')},
                            status=400)

    # Duplicate-buy guard: same group reserved in the last 10 seconds
    recent = LogOrder.objects.filter(
        user=request.user, group=group, status='waiting',
        created_at__gte=timezone.now() - timedelta(seconds=10),
    ).exists()
    if recent:
        return JsonResponse({'success': False,
                             'error': 'Your previous request is still processing.'}, status=400)

    order = LogOrder.objects.create(
        user=request.user,
        group=group,
        group_name=group.name,
        description=group.description or '',
        price=group.price,
        credentials='',
        status='waiting',
    )
    logger.info('Log order %s reserved (user %s, group %s)',
                order.order_id, request.user.id, group.id)

    # Attempt immediate delivery - same transaction, so any failure
    # rolls back cleanly and the customer is never charged without creds.
    ok, new_balance, err = _deliver_order(order)
    if ok:
        return JsonResponse({'success': True, 'status': 'completed',
                             'order_id': order.order_id,
                             'creds': order.credentials,
                             'format_label': group.format_labels,
                             'price': str(order.price),
                             'new_balance': str(new_balance)})
    return JsonResponse({'success': False, 'error': err}, status=400)


@login_required
@require_POST
@transaction.atomic
def deliver_log(request, pk):
    """Fallback delivery for a waiting order (network retries, page reloads).

    Returns creds when completed; business failures cancel the order."""
    order = get_object_or_404(
        LogOrder.objects.select_for_update().select_related('group'),
        pk=pk, user=request.user,
    )

    if order.status == 'completed' and order.credentials:
        return JsonResponse({'success': True, 'status': 'completed',
                             'order_ref': order.order_id,
                             'creds': order.credentials,
                             'format_label': order.group.format_labels if order.group else ''})

    if order.status != 'waiting':
        return JsonResponse({'success': False, 'status': order.status,
                             'error': 'This order is no longer active.'}, status=400)

    ok, new_balance, err = _deliver_order(order)
    if ok:
        return JsonResponse({'success': True, 'status': 'completed',
                             'order_id': order.order_id,
                             'creds': order.credentials,
                             'format_label': order.group.format_labels if order.group else '',
                             'price': str(order.price),
                             'new_balance': str(new_balance)})
    return JsonResponse({'success': False, 'status': order.status, 'error': err}, status=400)


@login_required
@require_POST
@transaction.atomic
def cancel_log_order(request, pk):
    """Cancel a waiting order. Nothing was debited, so cancel is always free
    and credentials were never removed from stock."""
    order = get_object_or_404(LogOrder, pk=pk, user=request.user)

    if order.status == 'cancelled':
        return JsonResponse({'success': True, 'message': 'Already cancelled.'})

    if order.status != 'waiting':
        return JsonResponse({'success': False,
                             'error': 'This order can no longer be cancelled.'}, status=400)

    order.status = 'cancelled'
    order.save(update_fields=['status'])
    logger.info('Log order %s cancelled (user %s)', order.order_id, request.user.id)
    return JsonResponse({'success': True, 'message': 'Order cancelled. No charge was made.'})


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
def marketplace(request):
    wallet = getattr(request.user, 'wallet', None)
    return render(request, 'marketplace/buynumber.html', {
        'countries': Country.objects.filter(is_active=True).order_by('name'),
        'active_orders': NumberOrder.objects.filter(
            user=request.user, status='active'),
        'balance': wallet.balance if wallet else 0,
    })