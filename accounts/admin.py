from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'phone', 'is_verified',
                    'is_staff', 'date_joined')
    list_filter = ('is_verified', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'phone')
    readonly_fields = ('date_joined', 'last_login')
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal', {'fields': ('phone',)}),
        ('PocketFi account', {'fields': ('pocketfi_account_number', 'pocketfi_bank_name')}),
        ('Flags', {'fields': ('is_verified', 'is_active', 'is_staff', 'is_superuser')}),
        ('Timestamps', {'fields': ('date_joined', 'last_login'), 'classes': ('collapse',)}),
    )