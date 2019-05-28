import logging
import time
import xml.etree.ElementTree
from io import StringIO

from django.core.management import BaseCommand

from gardener.data.models import Location
from gardener.data.models import WeatherForecast
from gardener.data.models import WeatherForecastProvider
from gardener.utils import ftp_get
from gardener.utils import http_get

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Set weather forecasts based on data provided by weather forecast provider.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-once',
            action='store_true',
            default=False,
            help='Update once and exit.')

        parser.add_argument(
            '--delay',
            type=int,
            required=False,
            default=600,
            help='Delay in seconds for periodical update.')

    def handle(self, *args, **options):
        run_once = options['run_once']
        delay = options['delay']

        while True:
            weather_forecast_providers = WeatherForecastProvider.objects.all()
            for weather_forecast_provider in weather_forecast_providers:
                weather_forecasts = None

                if weather_forecast_provider.name == 'bom.gov.au':
                    weather_forecasts = get_bom_gov_au_weather_forecasts(weather_forecast_provider.url)
                else:
                    raise NotImplementedError(
                        f'Need new method in update_weather_forecast.py for {weather_forecast_provider.name}')

                if weather_forecasts:
                    for row in weather_forecasts:
                        obj, created = WeatherForecast.objects.update_or_create(
                            location=row['location'],
                            start_time=row['start_time'],
                            end_time=row['end_time'],
                            temp_unit=row['temp_unit'],
                            defaults=dict(min_temp=row['min_temp'], max_temp=row['max_temp'], pop=row['pop']))
                        if created:
                            logger.info(f'obj={obj}')

            if run_once:
                break

            logger.debug(f'sleeping for {delay}s')
            time.sleep(delay)


def get_bom_gov_au_weather_forecasts(url):
    weather_forecasts = []

    if url.startswith('ftp'):
        xml_content = ftp_get(url)
    else:
        response = http_get(url)
        xml_content = response.text

    with StringIO(xml_content) as xml_file:
        root = xml.etree.ElementTree.parse(xml_file).getroot()
        areas = root.findall('forecast')[0].findall('area')
        for area in areas:
            try:
                location = Location.objects.get(name=area.get('description'))
            except Location.DoesNotExist:
                continue

            for forecast in area.findall('forecast-period'):
                index = forecast.get('index')

                if index == 0:  # Skip today's partial.
                    continue

                start_time = forecast.get('start-time-utc')
                end_time = forecast.get('end-time-utc')
                min_temp = None
                max_temp = None
                pop = None

                for element in forecast.iter():
                    if element.get('type') == 'air_temperature_minimum':
                        min_temp = int(element.text)
                    if element.get('type') == 'air_temperature_maximum':
                        max_temp = int(element.text)
                    if element.get('type') == 'probability_of_precipitation':
                        pop = int(element.text.strip('%'))

                if not all([min_temp, max_temp, pop]):
                    continue

                weather_forecasts.append(dict(
                    location=location,
                    start_time=start_time,
                    end_time=end_time,
                    temp_unit='°C',
                    min_temp=min_temp,
                    max_temp=max_temp,
                    pop=pop))

    return weather_forecasts
