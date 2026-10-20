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
ALLOWED_HOSTS = ["pabloexchange.onrender.com", "localhost", "127.0.0.1"]

# ← NEW: required by Django 4+ when requests come via https:// domain (fixes CSRF "origin not trusted" errors)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://pabloexchange.onrender.com,https://pabloexchange.com,https://www.pabloexchange.com',
    cast=Csv(),
)


INSTALLED_APPS = [
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
]

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
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
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