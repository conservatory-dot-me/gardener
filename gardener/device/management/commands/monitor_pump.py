import logging
import time

from django.core.management import BaseCommand

from gardener.device.models import Pump

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Monitor and stop running pump.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-once',
            action='store_true',
            default=False,
            help='Check once and exit.')

        parser.add_argument(
            '--delay',
            type=int,
            required=False,
            default=5,
            help='Delay in seconds for periodical check.')

    def handle(self, *args, **options):
        run_once = options['run_once']
        delay = options['delay']

        while True:
            pumps = Pump.objects.all()
            for pump in pumps:
                status = pump.status
                if status == Pump.TIMED_OUT:
                    logger.info(f'stopping pump={pump} due to status={status}')
                    pump.stop()
                elif status == Pump.OFF and pump.gpio_value(pump.gpio_export_num) != Pump.OFF:
                    logger.warning(f'force stopping pump={pump}')
                    pump.stop(force=True)

            if run_once:
                break

            logger.debug(f'sleeping for {delay}s')
            time.sleep(delay)
