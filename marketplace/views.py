import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

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
    """Deliver a log order inside the caller's atomic block: pop one unsold
    item, debit the wallet, mark completed. Returns (ok, new_balance, error).
    On any failure the caller's transaction rolls back — nothing is charged
    and the item stays in stock."""
    group = order.group
    if group is None:
        return False, None, 'This product is no longer available.'

    item = (LogItem.objects
            .select_for_update()
            .filter(group=group, is_sold=False)
            .order_by('id')
            .first())
    if item is None:
        group.stock = 0
        group.save(update_fields=['stock'])
        return False, None, 'Item is sold out.'

    if not can_afford(order.user, order.price):
        balance = getattr(getattr(order.user, 'wallet', None), 'balance', 0) or 0
        return False, None, (f'Insufficient funds. This order costs \u20A6{order.price:,.2f} '
                             f'but your balance is \u20A6{balance:,.2f}.')

    # Debit only now — credentials are guaranteed in hand.
    debit(order.user, order.price,
          description=f'Purchase of {group.name} ({order.order_id})',
          meta={'group_id': group.id, 'order_id': order.id})

    item.is_sold = True
    item.sold_at = timezone.now()
    item.save(update_fields=['is_sold', 'sold_at'])

    group.stock = max(0, group.stock - 1)
    group.save(update_fields=['stock'])

    order.item = item                    # DB-enforced: one item, one sale
    order.credentials = item.content
    order.status = 'completed'
    order.save(update_fields=['item', 'credentials', 'status'])

    logger.info('Log order %s delivered (user %s, group %s)',
                order.order_id, order.user_id, group.id)
    return True, get_balance(order.user), None


@login_required
@require_POST
@transaction.atomic
def purchase_log(request, pk):
    """Buy a log: validate stock + balance, create the order, deliver it —
    all in one atomic transaction.

    Success returns the credentials immediately. ANY failure rolls the whole
    thing back: no order, no charge, stock untouched, and the customer sees
    the exact reason."""
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

    if not can_afford(request.user, group.price):
        balance = getattr(getattr(request.user, 'wallet', None), 'balance', 0) or 0
        return JsonResponse({'success': False,
                             'error': (f'Insufficient funds. You need \u20A6{group.price:,.2f} '
                                       f'but your balance is \u20A6{balance:,.2f}.')},
                            status=400)

    order = LogOrder.objects.create(
        user=request.user,
        group=group,
        group_name=group.name,
        description=group.description or '',
        price=group.price,
        credentials='',
        status='waiting',   # transient: completed by _deliver_order in this same transaction
    )
    logger.info('Log order %s reserved (user %s, group %s)',
                order.order_id, request.user.id, group.id)

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
def deliver_log(request, pk):
    """Re-fetch credentials for a completed log order (page reloads, lost
    connections). Log orders complete instantly at purchase time — there is
    no waiting or re-delivery state."""
    order = get_object_or_404(
        LogOrder.objects.select_related('group'),
        pk=pk, user=request.user,
    )

    if order.status == 'completed' and order.credentials:
        return JsonResponse({'success': True, 'status': 'completed',
                             'order_ref': order.order_id,
                             'creds': order.credentials,
                             'format_label': order.group.format_labels if order.group else ''})

    return JsonResponse({'success': False, 'status': order.status,
                         'error': 'This order is no longer available.'}, status=400)