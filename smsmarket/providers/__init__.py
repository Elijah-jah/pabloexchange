from django.conf import settings

from .daisysms import DaisySmsProvider
from .dummy import DummyProvider
from .instantnums import InstantNumsProvider

_PROVIDERS = {
    'daisysms': DaisySmsProvider,
    'instantnums': InstantNumsProvider,
    'dummy': DummyProvider,
}

def get_provider(name=None):
    name = name or getattr(settings, 'SMS_PROVIDER', 'dummy')
    return _PROVIDERS[name]()