from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings_view, name='settings'),
    path(
    'forgot-password/',
    views.PabloPasswordResetView.as_view(),
    name='password_reset',
),
path(
    'forgot-password/sent/',
    views.PabloPasswordResetDoneView.as_view(),
    name='password_reset_done',
),
path(
    'reset/<uidb64>/<token>/',
    views.PabloPasswordResetConfirmView.as_view(),
    name='password_reset_confirm',
),
path(
    'reset/done/',
    views.PabloPasswordResetCompleteView.as_view(),
    name='password_reset_complete',
),
]