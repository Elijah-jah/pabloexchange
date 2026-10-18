"""
PocketFi payment integration.

NOTE: endpoints follow a standard hosted-checkout pattern. Adjust
paths/fields to PocketFi's actual API docs when credentials arrive.
"""
import requests
from django.conf import settings


def create_payment(user, amount, reference):
    """Create a hosted-checkout payment. Returns {'checkout_url': ...} or {}."""
    if not settings.POCKETFI_SECRET_KEY:
        # Dev fallback: no keys configured -> route to local dev-confirm page
        return {'checkout_url': None, 'dev_mode': True}

    resp = requests.post(
        f'{settings.POCKETFI_BASE_URL}/payments',
        headers={'Authorization': f'Bearer {settings.POCKETFI_SECRET_KEY}'},
        json={
            'amount': str(amount),
            'currency': settings.CURRENCY,
            'reference': reference,
            'customer_email': user.email,
            'callback_url': settings.POCKETFI_CALLBACK_URL,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {'checkout_url': data.get('checkout_url') or data.get('data', {}).get('checkout_url')}


def verify_payment(reference):
    """Server-side fallback if the webhook is ever missed."""
    resp = requests.get(
        f'{settings.POCKETFI_BASE_URL}/payments/{reference}',
        headers={'Authorization': f'Bearer {settings.POCKETFI_SECRET_KEY}'},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()