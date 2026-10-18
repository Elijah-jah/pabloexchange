from .services import balance


def global_balance(request):
    if request.user.is_authenticated:
        return {'balance': balance(request.user)}
    return {'balance': None}