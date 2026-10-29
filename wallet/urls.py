from django.urls import path

from . import views


app_name = 'wallet'

urlpatterns = [
    path('fund/', views.fund_wallet, name='fund'),
    path('deposit/', views.fund_wallet, name='deposit'),
    path(
        'account-details/',
        views.add_account_details,
        name='add_account_details',
    ),
    path('verify/', views.verify_payment, name='verify_payment'),
    path(
        'payments/pocketfi/callback/',
        views.pocketfi_callback,
        name='pocketfi_callback',
    ),
    path(
        'payments/pocketfi/dev-confirm/<str:reference>/',
        views.dev_confirm,
        name='pocketfi_dev_confirm',
    ),
    path('transactions/', views.transactions, name='transactions'),
    path('balance/', views.wallet_balance_json, name='wallet_balance_json'),
]