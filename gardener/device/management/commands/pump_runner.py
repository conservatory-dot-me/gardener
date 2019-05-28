import logging
import time

from django.conf import settings
from django.core.management import BaseCommand

from gardener.device.models import Pump

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Start or stop pump based on its status in Redis.'

    def handle(self, *args, **options):
        last_keys = None

        pubsub = settings.REDIS_CONN.pubsub()
        pubsub.psubscribe(f'__keyspace@*:{settings.REDIS_KEY_PREFIX}:*')

        while True:
            now_ms = time.time() * 1000

            # Loop through pump keys every second to ensure keys are expired in a timely manner.
            if last_keys is None or (now_ms - last_keys >= 1000):
                keys = []
                cursor = 0
                while True:
                    cursor, partial_keys = settings.REDIS_CONN.scan(cursor, f'{settings.REDIS_KEY_PREFIX}:pump:*', 100)
                    keys.extend(partial_keys)
                    if cursor == 0:
                        break
                logger.debug(f'keys={keys}')
                last_keys = now_ms

            msg = pubsub.get_message()
            if msg is None:
                time.sleep(0.01)  # 10 ms artificial intrinsic latency.
                continue

            (pump_id, pump_status) = Pump.parse_redis_pubsub_msg(msg)
            if pump_id is not None and pump_status is not None:
                pump = Pump.objects.get(id=pump_id)
                pump.set_gpio_value(pump.gpio_export_num, pump_status)
