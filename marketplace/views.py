from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from countries.models import Country
from smsmarket.models import NumberOrder
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from pricing.models import Pricing
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from wallet.services import can_afford, debit

from .models import (LogCategory, LogCredential, LogGroup, LogItem, LogOrder,
                     LogSubCategory)


@login_required
def marketplace_logs(request):
    """Account Logs Shop — sections grouped by subcategory."""
    categories = LogCategory.objects.filter(is_active=True).prefetch_related('subcategories')

    sections = []
    subs = (LogSubCategory.objects
            .filter(is_active=True, category__is_active=True,
                    groups__is_active=True, groups__items__is_active=True)
            .distinct()
            .order_by('order', 'name'))
    for sub in subs:
        items = (LogItem.objects
                 .filter(group__subcategory=sub, is_active=True)
                 .select_related('group')
                 .order_by('title'))
        if not items.exists():
            continue
        sections.append({
            'key': f'sub-{sub.id}',
            'name': sub.name,
            'products': [{
                'id': it.id,
                'title': it.title,
                'price': it.price,
                'stock': it.stock,
                'description': it.description or it.group.description,
                'image': it.display_image,
                'format_labels': it.display_format,
                'category_id': sub.category_id,
            } for it in items],
        })

    return render(request, 'marketplace/logs.html', {
        'categories': categories,
        'sections': sections,
        'user_wallet': getattr(request.user, 'wallet', None),
    })


class StockError(Exception):
    pass


class InsufficientFundsLogs(Exception):
    pass


@login_required
@transaction.atomic
def purchase_log(request, pk):
    """Buy one unit of a log item: debit wallet, decrement stock,
    mark credential sold, return the credentials as JSON."""
    item = (LogItem.objects
            .select_for_update()
            .select_related('group', 'group__subcategory')
            .get(pk=pk, is_active=True))

    if item.stock <= 0:
        return JsonResponse({'success': False, 'error': 'Item is sold out.'}, status=400)

    if not can_afford(request.user, item.price):
        return JsonResponse({'success': False,
                             'error': 'Insufficient wallet balance. Please fund your wallet.'},
                            status=400)

    # Oldest unsold credential wins
    cred = (LogCredential.objects
            .select_for_update()
            .filter(item=item, is_sold=False)
            .order_by('id')
            .first())
    if cred is None:
        # DB stock inconsistent — trust the credential count
        item.stock = LogCredential.objects.filter(item=item, is_sold=False).count()
        item.save(update_fields=['stock'])
        return JsonResponse({'success': False, 'error': 'Item is sold out.'}, status=400)

    debit(request.user, item.price,
          description=f'{item.title} (log)',
          meta={'item_id': item.id})

    cred.is_sold = True
    cred.sold_at = timezone.now()
    cred.save(update_fields=['is_sold', 'sold_at'])

    item.stock = max(0, item.stock - 1)
    if item.stock == 0:
        item.is_active = False          # hide sold-out listings from the shop
    item.save(update_fields=['stock', 'is_active'])

    order = LogOrder.objects.create(
        user=request.user,
        item=item,
        item_title=item.title,
        price=item.price,
        credentials=cred.content,
    )

    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'creds': cred.content,
        'format_label': item.display_format,
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
    return render(request, 'marketplace/buynumber.html', {
        # ALL active countries — your JS already handles "no services" gracefully
        'countries': Country.objects.filter(is_active=True).order_by('name'),
        'active_orders': NumberOrder.objects.filter(
            user=request.user, status='active'),
        # balance pill in your header reads this — adapt to your wallet relation
        'balance': request.user.wallet.balance,
    })


