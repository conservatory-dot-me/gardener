import logging
import time

from django.core.management import BaseCommand
from django.utils import timezone

from gardener.device.models import ScheduledRun
from gardener.utils import send_email_notification

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Start pump at scheduled time.'

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
            scheduled_runs = ScheduledRun.objects \
                .filter(
                    pump__device__is_active=True,
                    pump__is_active=True,
                    run__isnull=True,
                    start_time__lte=timezone.now()) \
                .select_related('pump')
            for scheduled_run in scheduled_runs:
                run = scheduled_run.pump.start(scheduled_run=scheduled_run)
                if run is None:
                    continue
                subject = f'Scheduled run started - Run #{run.id}'
                message = f'Pump {run.pump.name} has started running for {scheduled_run.duration}s'
                recipients = scheduled_run.pump.scheduled_run_email_notification_recipients
                weather_forecast = scheduled_run.weather_forecast
                if weather_forecast:
                    message += (
                        '\n\n'
                        f'Weather forecast\n'
                        f'Min. temp: {weather_forecast.min_temp}{weather_forecast.temp_unit}\n'
                        f'Max. temp: {weather_forecast.max_temp}{weather_forecast.temp_unit}\n'
                        f'POP: {weather_forecast.pop}')
                if recipients:
                    send_email_notification(subject, message, recipients)

            if run_once:
                break

            logger.debug(f'sleeping for {delay}s')
            time.sleep(delay)
