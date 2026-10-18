from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .forms import SignUpForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse



@login_required
def settings_view(request):
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        # ---------- Profile ----------
        if action == 'profile':
            username = request.POST.get('username', '').strip()
            phone = request.POST.get('phone', '').strip()
            if len(username) < 3:
                return JsonResponse({'ok': False, 'error': 'Username must be at least 3 characters.'}, status=400)
            if get_user_model().objects.filter(username=username).exclude(pk=user.pk).exists():
                return JsonResponse({'ok': False, 'error': 'That username is already taken.'}, status=400)
            user.username = username
            user.phone = phone
            user.save(update_fields=['username', 'phone'])
            return JsonResponse({'ok': True, 'message': 'Profile updated.'})

        # ---------- Password ----------
        if action == 'password':
            current = request.POST.get('current_password', '')
            new1 = request.POST.get('new_password1', '')
            new2 = request.POST.get('new_password2', '')
            if not user.check_password(current):
                return JsonResponse({'ok': False, 'error': 'Your current password is incorrect.'}, status=400)
            if new1 != new2:
                return JsonResponse({'ok': False, 'error': 'New passwords do not match.'}, status=400)
            try:
                validate_password(new1, user)
            except ValidationError as e:
                return JsonResponse({'ok': False, 'error': '; '.join(e.messages)}, status=400)
            user.set_password(new1)
            user.save(update_fields=['password'])
            update_session_auth_hash(request, user)
            return JsonResponse({'ok': True, 'message': 'Password changed.'})

        # ---------- Notifications ----------
        if action == 'preferences':
            prefs = user.preferences or {}
            prefs['notify_order_updates'] = request.POST.get('notify_order_updates') == 'on'
            prefs['notify_promos'] = request.POST.get('notify_promos') == 'on'
            user.preferences = prefs
            user.save(update_fields=['preferences'])
            return JsonResponse({'ok': True, 'message': 'Preferences saved.'})

    return render(request, 'accounts/settings.html', {
        'prefs': user.preferences or {},
    })


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    error = ''
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get('next') or 'dashboard')
        error = 'Invalid email or password.'
    return render(request, 'accounts/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('home')


