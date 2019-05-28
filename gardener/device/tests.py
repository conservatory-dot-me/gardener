import logging
import uuid
from datetime import datetime
from datetime import time
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import Client
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from gardener.data.models import Location
from gardener.data.models import WeatherForecast
from gardener.data.models import WeatherForecastProvider
from gardener.device.models import Device
from gardener.device.models import Light
from gardener.device.models import PopToPumpDuration
from gardener.device.models import Pump
from gardener.device.models import Run
from gardener.device.models import ScheduledRun
from gardener.utils import get_next_sun

logger = logging.getLogger('gardener')


@mock.patch('gardener.utils.EmailThread.run', return_value=None)  # Skip thread.
class DeviceTestCase(TransactionTestCase):
    def setUp(self):
        self.lat = -33.8468332
        self.lon = 151.0635537

        self.weather_forecast_provider = WeatherForecastProvider.objects.create(
            name='test-weather-forecast-provider')

        self.location = Location.objects.create(
            name='test-location',
            weather_forecast_provider=self.weather_forecast_provider)

        self.device = Device.objects.create(
            name=uuid.uuid4(),
            location=self.location,
            latitude=self.lat,
            longitude=self.lon)

        self.pump_1 = Pump.objects.create(
            device=self.device,
            gpio_export_num=1,
            scheduled_run_frequency=Pump.DAILY)

        self.pump_2 = Pump.objects.create(
            device=self.device,
            gpio_export_num=2,
            scheduled_run_frequency=Pump.THREE_HOURLY)

        self.light_1 = Light.objects.create(
            device=self.device,
            gpio_export_num=3,
            start_time=time(15, 0),
            duration=43200)

        self.light_2 = Light.objects.create(
            device=self.device,
            gpio_export_num=4,
            start_time=time(10, 30),
            duration=43200)

        self.client = Client()

    @mock.patch.object(
        timezone,
        'now',
        return_value=datetime.strptime('2018-09-08T10:32:05+1000', '%Y-%m-%dT%H:%M:%S%z'))
    def test_schedule_run(self, *args):
        PopToPumpDuration.objects.create(pump=self.pump_1, pop=30, duration=240)
        PopToPumpDuration.objects.create(pump=self.pump_1, pop=60, duration=180)
        PopToPumpDuration.objects.create(pump=self.pump_1, pop=90, duration=120)

        forecast_start_time = timezone.now()
        forecast_end_time = forecast_start_time + timedelta(hours=24)
        WeatherForecast.objects.create(
            location=self.location,
            start_time=forecast_start_time,
            end_time=forecast_end_time,
            pop=50)

        call_command('schedule_run', run_once=True)

        next_sunrise, next_sunset = get_next_sun(self.lat, self.lon)
        self.assertEqual(ScheduledRun.objects.count(), 2)

        scheduled_run = ScheduledRun.objects.first()
        self.assertEqual(scheduled_run.pump.gpio_export_num, self.pump_1.gpio_export_num)
        self.assertEqual(scheduled_run.start_time, next_sunrise)
        self.assertIsNotNone(scheduled_run.weather_forecast)
        self.assertEqual(scheduled_run.duration, 180)

        scheduled_run = ScheduledRun.objects.last()
        self.assertEqual(scheduled_run.pump.gpio_export_num, self.pump_2.gpio_export_num)
        self.assertEqual((scheduled_run.start_time - timezone.now()).total_seconds(), 8875)
        self.assertIsNotNone(scheduled_run.weather_forecast)
        self.assertEqual(scheduled_run.duration, 60)

    @mock.patch.object(
        timezone,
        'now',
        return_value=datetime.strptime('2018-09-08T10:32:05+1000', '%Y-%m-%dT%H:%M:%S%z'))
    def test_execute_scheduled_run(self, *args):
        weather_forecast = WeatherForecast.objects.create(
            location=self.location, start_time=timezone.now(), end_time=timezone.now(), pop=50)
        scheduled_run = ScheduledRun.objects.create(
            pump=self.pump_1, weather_forecast=weather_forecast, start_time=timezone.now(), duration=0.1)
        call_command('execute_scheduled_run', run_once=True)
        run = Run.objects.latest('start_time')
        self.assertEqual(run.pump, scheduled_run.pump)
        self.assertEqual(run.start_time, scheduled_run.start_time)
        self.assertEqual(run.scheduled_run, scheduled_run)

    def test_monitor_pump(self, *args):
        self.client.post(reverse('start-pump', args=(self.pump_1.id, )))

        run = Run.objects.latest('start_time')
        self.assertEqual(self.pump_1.status, Pump.ON)
        self.assertEqual(run.pump, self.pump_1)
        self.assertIsNone(run.end_time)
        self.assertIsNone(run.scheduled_run)

        run.start_time = timezone.now() - timedelta(seconds=self.pump_1.max_duration)
        run.save()
        self.assertEqual(self.pump_1.status, Pump.TIMED_OUT)

        call_command('monitor_pump', run_once=True)

        run.refresh_from_db()
        self.assertIsNotNone(run.end_time)
        self.assertEqual(self.pump_1.status, Pump.OFF)

    def test_start_stop(self, *args):
        response = self.client.post(reverse('start-pump', args=(self.pump_1.id, )))
        self.assertEqual(response.json()['id'], self.pump_1.id)
        self.assertTrue(Run.objects.count(), 1)

        self.client.post(reverse('start-pump', args=(self.pump_1.id, )))
        self.assertTrue(Run.objects.count(), 1)

        self.client.post(reverse('stop-pump', args=(self.pump_1.id, )))
        self.assertTrue(Run.objects.count(), 1)

        run = Run.objects.first()
        self.assertTrue(run.start_time < run.end_time)

        response = self.client.post(reverse('start-pump', args=(2, )))
        self.assertEqual(response.status_code, 404)

    @mock.patch.object(
        timezone,
        'now',
        return_value=datetime.strptime('2018-09-08T10:32:05+1000', '%Y-%m-%dT%H:%M:%S%z'))
    def test_weather_forecasts(self, *args):
        WeatherForecast.objects.create(
            location=self.location,
            start_time=timezone.now(),
            end_time=timezone.now(),
            min_temp=8,
            max_temp=17,
            pop=40)
        response = self.client.get(reverse('weather-forecasts', args=(self.device.id, )))
        self.assertEqual(response.json(), [[1536366725, '°C', 8, 17, 40]])

    @mock.patch.object(Light, 'set_gpio_value')
    @mock.patch.object(Light, 'gpio_value', return_value=Light.OFF)
    @mock.patch.object(
        timezone,
        'now',
        return_value=datetime.strptime('2018-09-08T02:32:05+1000', '%Y-%m-%dT%H:%M:%S%z'))
    def test_light_runner_1(self, mock_timezone_now, mock_gpio_value, mock_set_gpio_value, *args):
        # 15:00 -> 03:00
        # now 02:32 => start
        call_command('light_runner', run_once=True)
        mock_set_gpio_value.assert_called_with(self.light_1.gpio_export_num, Light.ON)

    @mock.patch.object(Light, 'set_gpio_value')
    @mock.patch.object(Light, 'gpio_value', return_value=Light.ON)
    @mock.patch.object(
        timezone,
        'now',
        return_value=datetime.strptime('2018-09-08T10:28:05+1000', '%Y-%m-%dT%H:%M:%S%z'))
    def test_light_runner_2(self, mock_timezone_now, mock_gpio_value, mock_set_gpio_value, *args):
        # 10:30 -> 22:30
        # now 10:28 => stop
        call_command('light_runner', run_once=True)
        mock_set_gpio_value.assert_called_with(self.light_2.gpio_export_num, Light.OFF)
