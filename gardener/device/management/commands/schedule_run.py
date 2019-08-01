import logging
import time
from datetime import timedelta

from django.core.management import BaseCommand
from django.db.models import F
from django.db.models import Func
from django.utils import timezone

from gardener.data.models import WeatherForecast
from gardener.device.models import PopToPumpDuration
from gardener.device.models import Pump
from gardener.device.models import ScheduledRun
from gardener.utils import get_next_sun

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Schedule pump to run automatically.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-once',
            action='store_true',
            default=False,
            help='Schedule once and exit.')

        parser.add_argument(
            '--delay',
            type=int,
            required=False,
            default=60,
            help='Delay in seconds for periodical scheduling.')

    def handle(self, *args, **options):
        run_once = options['run_once']
        delay = options['delay']

        while True:
            pumps = Pump.objects \
                .filter(device__is_active=True, is_active=True, scheduled_run_frequency__isnull=False) \
                .select_related('device', 'device__location')
            for pump in pumps:
                freq = pump.scheduled_run_frequency  # Days.

                try:
                    last_start_time = ScheduledRun.objects.filter(pump=pump).latest('start_time').start_time
                    if last_start_time > timezone.now():
                        continue
                except ScheduledRun.DoesNotExist:
                    last_start_time = timezone.now()
                last_start_time = last_start_time.replace(minute=0, second=0, microsecond=0)  # Hourly precision.

                if freq in (Pump.DAILY, Pump.WEEKLY, Pump.MONTHLY):
                    while True:
                        next_start_time, _ = get_next_sun(
                            pump.device.latitude,
                            pump.device.longitude,
                            date=last_start_time + timedelta(days=freq - 1))
                        if next_start_time <= timezone.now():
                            last_start_time += timedelta(days=1)
                        else:
                            break
                else:
                    while True:
                        next_start_time = last_start_time + timedelta(seconds=freq * 86400)
                        if next_start_time <= timezone.now():
                            last_start_time = next_start_time
                        else:
                            break

                # Get forecast nearest to next_start_time.
                min_forecast_time = next_start_time - timedelta(hours=24)
                max_forecast_time = next_start_time + timedelta(hours=24)
                weather_forecast = WeatherForecast.objects \
                    .filter(location=pump.device.location, start_time__range=(min_forecast_time, max_forecast_time)) \
                    .annotate(delta=F('start_time') - next_start_time) \
                    .order_by('delta') \
                    .first()

                duration = pump.scheduled_run_default_duration
                if weather_forecast is not None:
                    forecast_pop = weather_forecast.pop
                    # Get duration nearest to forecast_pop.
                    pop_to_pump_duration = PopToPumpDuration.objects \
                        .filter(pump=pump) \
                        .annotate(delta=Func(F('pop') - forecast_pop, function='ABS')) \
                        .order_by('delta') \
                        .first()
                    if pop_to_pump_duration:
                        duration = pop_to_pump_duration.duration

                obj, created = ScheduledRun.objects.update_or_create(
                    pump=pump,
                    start_time=next_start_time,
                    defaults=dict(weather_forecast=weather_forecast, duration=duration))
                if created:
                    logger.info(f'obj={obj}')

            if run_once:
                break

            logger.debug(f'sleeping for {delay}s')
            time.sleep(delay)
