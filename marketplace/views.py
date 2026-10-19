from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from countries.models import Country
from smsmarket.models import NumberOrder
from pricing.models import Pricing
from wallet.services import can_afford, debit

from .models import LogCategory, LogGroup, LogItem, LogOrder, LogSubCategory


@login_required
def marketplace_logs(request):
    """Account Logs Shop — sections grouped by subcategory, cards = groups."""
    categories = LogCategory.objects.filter(is_active=True)

    # Prefetch groups with their real (unsold-item) stock in one query,
    # so building the product list below triggers zero extra DB hits.
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
                  .annotate(actual_stock=Count('items', filter=Q(items__is_sold=False)))
                  .order_by('name'))
        products = [{
            'id': g.id,
            'title': g.name,
            'price': g.price,
            # Authoritative stock = unsold credential lines; fall back to
            # the stored counter only if it is somehow lower.
            'stock': max(g.actual_stock, g.stock),
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


@login_required
@transaction.atomic
def purchase_log(request, pk):
    """Buy one unit of a group: debit wallet, pop oldest unsold LogItem,
    decrement stock, snapshot the order."""
    group = get_object_or_404(
        LogGroup.objects
        .select_for_update()
        .select_related('subcategory'),
        pk=pk, is_active=True,
    )

    # Stock of record: unsold items. Sync the stored counter if it drifted.
    real_stock = group.items.filter(is_sold=False).count()
    if group.stock != real_stock:
        group.stock = real_stock
        group.save(update_fields=['stock'])

    if real_stock <= 0:
        return JsonResponse({'success': False, 'error': 'Item is sold out.'}, status=400)

    if not can_afford(request.user, group.price):
        return JsonResponse({'success': False,
                             'error': 'Insufficient wallet balance. Please fund your wallet.'},
                            status=400)

    item = (LogItem.objects
            .select_for_update()
            .filter(group=group, is_sold=False)
            .order_by('id')
            .first())
    if item is None:  # lost a race — another buyer took the last item
        group.stock = 0
        group.is_active = False
        group.save(update_fields=['stock', 'is_active'])
        return JsonResponse({'success': False, 'error': 'Item is sold out.'}, status=400)

    debit(request.user, group.price,
          description=f'{group.name} (log)',
          meta={'group_id': group.id})

    item.is_sold = True
    item.sold_at = timezone.now()
    item.save(update_fields=['is_sold', 'sold_at'])

    group.stock = max(0, group.stock - 1)
    if group.stock == 0:
        group.is_active = False          # hide sold-out card from the shop
    group.save(update_fields=['stock', 'is_active'])

    order = LogOrder.objects.create(
        user=request.user,
        group=group,
        group_name=group.name,
        price=group.price,
        credentials=item.content,
    )

    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'creds': item.content,
        'format_label': group.format_labels,
        'new_balance': str(getattr(request.user.wallet, 'balance', 0)),
    })


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
    wallet = getattr(request.user, 'wallet', None)
    return render(request, 'marketplace/buynumber.html', {
        # ALL active countries — your JS already handles "no services" gracefully
        'countries': Country.objects.filter(is_active=True).order_by('name'),
        'active_orders': NumberOrder.objects.filter(
            user=request.user, status='active'),
        # balance pill in your header reads this — adapt to your wallet relation
        'balance': wallet.balance if wallet else 0,
    })