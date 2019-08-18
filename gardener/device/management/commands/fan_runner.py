import logging
import time
from datetime import datetime
from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from gardener.device.models import Fan
from gardener.utils import time_in_range

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Start fan at scheduled time.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-once',
            action='store_true',
            default=False,
            help='Execute once and exit.')

        parser.add_argument(
            '--delay',
            type=int,
            required=False,
            default=5,
            help='Delay in seconds for periodical execution.')

    def handle(self, *args, **options):
        run_once = options['run_once']
        delay = options['delay']

        while True:
            fans = Fan.objects.filter(is_active=False)
            for fan in fans:
                fan.stop()

            fans = Fan.objects.filter(device__is_active=True, is_active=True)
            for fan in fans:
                now = timezone.localtime().time()
                start_time = fan.start_time
                start_dt = datetime.combine(timezone.localtime().date(), start_time)
                end_time = (start_dt + timedelta(seconds=fan.duration)).time()

                if time_in_range(start_time, end_time, now):
                    fan.start()
                else:
                    fan.stop()

            if run_once:
                break

            logger.debug(f'sleeping for {delay}s')
            time.sleep(delay)
