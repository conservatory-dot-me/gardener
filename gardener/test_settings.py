from .settings import *  # noqa

REDIS_KEY_PREFIX = 'test_gardener'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,  # noqa
        'KEY_PREFIX': REDIS_KEY_PREFIX,
    },
}
