import environ
import os
import redis

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env_file = os.path.join(BASE_DIR, '.env')
if os.path.isfile(env_file):
    environ.Env.read_env(env_file)

SECRET_KEY = env('SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = ['*']

EMAIL_CONFIG = env.email_url('EMAIL_URL')
vars().update(EMAIL_CONFIG)
EMAIL_SUBJECT_PREFIX = '[Gardener] '
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='gardener@localhost')

INTERNAL_IPS = env.list('INTERNAL_IPS', default=[])

INSTALLED_APPS = [
    'gardener.apps.GardenerAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'debug_toolbar',
    'django_extensions',
    'rest_framework',
    'gardener.dashboard',
    'gardener.data',
    'gardener.device',
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gardener.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'gardener.context_processors.websocket_server',
            ],
        },
    },
]

WSGI_APPLICATION = 'gardener.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': env('POSTGRESQL_DB_HOST', default='localhost'),
        'PORT': env('POSTGRESQL_DB_PORT', default=5432),
        'NAME': env('POSTGRESQL_DB_NAME', default='gardener'),
        'USER': env('POSTGRESQL_DB_USER', default='gardener'),
        'PASSWORD': env('POSTGRESQL_DB_PASSWORD', default='gardener'),
        'CONN_MAX_AGE': 60,
    },
}

REDIS_URL = env('REDIS_URL', default='redis://127.0.0.1:6379/0')
REDIS_CONN = redis.StrictRedis.from_url(REDIS_URL)
REDIS_KEY_PREFIX = 'gardener'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': REDIS_KEY_PREFIX,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SESSION_COOKIE_AGE = 86400 * 30

SESSION_COOKIE_NAME = 'gardener-sessionid'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = env('TIME_ZONE', default='Australia/Sydney')

USE_I18N = True

USE_L10N = True

USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'gardener', 'media')

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'gardener', 'public')

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

LOG_LEVEL = env('LOG_LEVEL', default='INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format':
                '%(levelname)s - %(asctime)s - %(process)d.%(thread)d - %(filename)s - %(funcName)s - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'logfile': {
            'level': LOG_LEVEL,
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'log', 'gardener.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'gardener': {
            'handlers': ['console', 'logfile'],
            'level': LOG_LEVEL,
            'propagate': True,
        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}
if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] += (
        'rest_framework.renderers.BrowsableAPIRenderer',
    )

WEBSOCKET_HOST = env('WEBSOCKET_HOST', default='127.0.0.1')
WEBSOCKET_PORT = env('WEBSOCKET_PORT', default=8888)

LCD_TEXT_PATH = os.path.join(BASE_DIR, 'log', 'lcd_text.txt')
