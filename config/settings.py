"""
Django settings for config project.
"""

from pathlib import Path
from decouple import config, Csv

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------- Core security ----------------
SECRET_KEY = config('SECRET_KEY', default='django-insecure-(h4^rt%2c4lo8_r(2!!-c23(ei@vmw^5&^epp3i(a#d8r)f!1y')

# ← CHANGED: default is now False (production-safe). Turn True only in local .env
DEBUG = config('DEBUG', default=False, cast=bool)

# ← CHANGED: your domain
ALLOWED_HOSTS = [
    "pabloexchange.onrender.com",
    "pabloexchange.com",
    "www.pabloexchange.com",
    "localhost",
    "127.0.0.1",
]

# ← NEW: required by Django 4+ when requests come via https:// domain (fixes CSRF "origin not trusted" errors)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://pabloexchange.onrender.com,https://pabloexchange.com,https://www.pabloexchange.com',
    cast=Csv(),
)


INSTALLED_APPS = [
    'jazzmin',  
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # local
    'accounts',
    'wallet',
    'smsmarket',
    'marketplace',
    'pages',
    'countries',
    'pricing',
    'django.contrib.humanize',
    'django_apscheduler',
    'cloudinary_storage',
    'cloudinary',
]

SMS_MARGIN_MULTIPLIER = 1.4   # 1.4 = 40% markup on live provider prices; adjust freely

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # ← NEW: serves static files efficiently in production (pip install whitenoise)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'wallet.context_processors.global_balance',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True


# ---------------- Static files ----------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# ← NEW: where collectstatic gathers files for production
STATIC_ROOT = BASE_DIR / 'staticfiles'
# ← NEW: whitenoise compressed + cached storage
STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',   # ← media now lives on Cloudinary
    },
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}


# ---------------- Cloudinary (persistent media storage) ----------------
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY': config('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}

# ---------------- Production hardening (active only when DEBUG=False) ----------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True                      # ← NEW: force http→https
    SESSION_COOKIE_SECURE = True                    # ← NEW: cookies only over https
    CSRF_COOKIE_SECURE = True                       # ← NEW
    SECURE_HSTS_SECONDS = 31536000                  # ← NEW: browsers remember https for 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True           # ← NEW
    SECURE_HSTS_PRELOAD = True                      # ← NEW
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # ← NEW: needed behind nginx
    SECURE_CONTENT_TYPE_NOSNIFF = True              # ← NEW
    X_FRAME_OPTIONS = 'DENY'                        # ← NEW


# ---------------- Auth ----------------
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'


# ---------------- PabloExchange ----------------
SITE_NAME = 'PabloExchange'
CURRENCY = 'NGN'
CURRENCY_SYMBOL = '₦'

MIN_FUND_AMOUNT = config('MIN_FUND_AMOUNT', default=500, cast=int)
MAX_FUND_AMOUNT = config('MAX_FUND_AMOUNT', default=100000, cast=int)

POCKETFI_PUBLIC_KEY = config('POCKETFI_PUBLIC_KEY', default='')
POCKETFI_SECRET_KEY = config('POCKETFI_SECRET_KEY', default='')
POCKETFI_WEBHOOK_SECRET = config('POCKETFI_WEBHOOK_SECRET', default='')
POCKETFI_BASE_URL = config('POCKETFI_BASE_URL', default='https://api.pocketfi.example.com/v1')
# ← CHANGED: your live domain — PocketFi must send users back here after payment
POCKETFI_CALLBACK_URL = config('POCKETFI_CALLBACK_URL', default='https://pabloexchange.com/payments/pocketfi/callback/')

SMS_PROVIDER = config('SMS_PROVIDER', default='dummy')

DAISYSMS_API_KEY = config('DAISYSMS_API_KEY', default='')
INSTANTNUMS_API_KEY = config('INSTANTNUMS_API_KEY', default='')
INSTANTNUMS_BASE_URL = config('INSTANTNUMS_BASE_URL', default='https://instantnums.com')

# ---------------- Django Jazzmin (admin theme) ----------------
JAZZMIN_SETTINGS = {
    "site_title": "PabloExchange Admin",
    "site_header": "PabloExchange",
    "site_brand": "PabloExchange",
    "welcome_sign": "Welcome to PabloExchange Admin",
    "copyright": "PabloExchange Ltd",
    "search_model": ["auth.User", "smsmarket.NumberOrder", "marketplace.LogOrder"],
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
    ],
    "usermenu_links": [
        {"name": "View Site", "url": "/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "smsmarket", "marketplace", "pricing", "countries",
        "wallet", "accounts", "auth",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "accounts": "fas fa-id-card",
        "smsmarket": "fas fa-sim-card",
        "smsmarket.numberorder": "fas fa-phone-alt",
        "marketplace": "fas fa-store",
        "marketplace.logorder": "fas fa-receipt",
        "marketplace.loggroup": "fas fa-box-open",
        "pricing": "fas fa-tags",
        "countries": "fas fa-globe-africa",
        "wallet": "fas fa-wallet",
        "django_apscheduler": "fas fa-clock",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-teal",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-teal",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",   # dark admin matching your brand; try "flatly" for light
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
    "actions_sticky_top": True,
}
MEDIA_ROOT = config('MEDIA_ROOT', default=BASE_DIR / 'media')