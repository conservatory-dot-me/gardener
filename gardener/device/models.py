import logging
import os
import signal
import stat
from operator import itemgetter

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Func
from django.db.models.functions import Extract
from django.utils import timezone

from gardener.data.models import Location
from gardener.data.models import WeatherForecast
from gardener.exceptions import SignalException
from gardener.utils import datetime_to_unixtimestamp
from gardener.utils import get_local_time
from gardener.utils import get_next_sun
from gardener.utils import get_private_ip
from gardener.utils import get_public_ip
from gardener.utils import get_time_zone
from gardener.utils import InterruptHandlerThread
from gardener.utils import PollingThread
from gardener.utils import unixtimestamp_to_datetime

logger = logging.getLogger('gardener')


class DeviceManager(models.Manager):
    def primary_device(self):
        if self.get_queryset().filter(is_active=True).exists() > 0:
            return self.get_queryset().filter(is_active=True).first()
        return self.get_queryset().first()


class Device(models.Model):
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, help_text='Location for weather forecasts.')
    latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text='Latitude where the device is deployed.')
    longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text='Longitude where the device is deployed.')
    objects = DeviceManager()

    def __str__(self):
        return '<%s name=%s>' % (self.__class__.__name__, self.name)

    def __repr__(self):
        return str(self)

    @property
    def cpu_temp(self):
        path = '/sys/devices/virtual/thermal/thermal_zone0/temp'
        if os.path.isfile(path):
            value = int(int(open(path).read().strip()) / 1000)
            return value
        return None

    @property
    def time_zone(self):
        return get_time_zone(self.latitude, self.longitude)

    @property
    def local_time(self):
        return get_local_time(self.latitude, self.longitude)

    @property
    def public_ip(self):
        return get_public_ip()

    @property
    def next_sunrise(self):
        next_sunrise, _ = get_next_sun(self.latitude, self.longitude)
        return next_sunrise

    @property
    def next_sunset(self):
        _, next_sunset = get_next_sun(self.latitude, self.longitude)
        return next_sunset

    @property
    def pump_status(self):
        return [(pump.id, pump.status) for pump in self.pump_set.all()]

    @property
    def weather_forecasts(self):
        """Returns recent and upcoming weather forecasts."""
        now = datetime_to_unixtimestamp(timezone.now())
        return self.location.weatherforecast_set \
            .annotate(delta=Func(Extract('start_time', 'epoch') - now, function='ABS')) \
            .filter(delta__lte=86400 * 3) \
            .order_by('start_time')

    @property
    def snapshots(self):
        camera = self.camera_set.filter(is_active=True).first()
        snapshots = []
        if camera is not None:
            for index in range(camera.current_snapshot):
                path = os.path.join(camera.snapshots_dir, f'{index + 1}.{camera.snapshot_extension}')
                if not os.path.exists(path):
                    continue
                snapshots.append(dict(
                    num=index + 1,
                    path=path,
                    dt=unixtimestamp_to_datetime(os.stat(path)[stat.ST_CTIME]),
                    url=os.path.join(camera.snapshots_url, f'{index + 1}.{camera.snapshot_extension}')))
        if snapshots:
            snapshots = sorted(snapshots, key=itemgetter('num'), reverse=True)
        return snapshots


class Gpio(models.Model):
    # GPIO values (swapped during get/set when using active-low relay).
    OFF = 0
    ON = 1

    # GPIO directions.
    IN = 'in'
    OUT = 'out'

    # GPIO interrupt edge triggers.
    RISING = 'rising'
    FALLING = 'falling'
    BOTH = 'both'

    # Relay types.
    ACTIVE_HIGH = 1
    ACTIVE_LOW = 0

    relay_type = models.PositiveSmallIntegerField(default=ACTIVE_HIGH)

    class Meta:
        abstract = True

    def gpio_value(self, gpio_export_num):
        path = f'/sys/class/gpio/gpio{gpio_export_num}/value'
        if os.path.isfile(path):
            value = int(open(path).read().strip())
            assert value in (self.ON, self.OFF)
            if self.relay_type == self.ACTIVE_LOW:
                if value == 1:
                    return 0
                else:
                    return 1
            return value
        return 0

    def set_gpio_value(self, gpio_export_num, value, direction=None, edge=None):
        assert value in (None, self.ON, self.OFF)
        if direction is None:
            direction = self.OUT
        assert direction in (self.IN, self.OUT)
        assert edge in (None, self.RISING, self.FALLING, self.BOTH)
        logger.info(f'set gpio #{gpio_export_num} - value={value} - direction={direction} - edge={edge}')

        gpio_path = f'/sys/class/gpio/gpio{gpio_export_num}'
        gpio_direction_path = f'{gpio_path}/direction'
        gpio_value_path = f'{gpio_path}/value'
        gpio_edge_path = f'{gpio_path}/edge'

        if not os.path.islink(gpio_path):
            logger.debug(f'creating gpio #{gpio_export_num} file access')
            try:
                with open('/sys/class/gpio/export', 'w') as f:
                    f.write(f'{gpio_export_num}')
                    f.flush()
            except PermissionError as e:
                logger.error(f'gpio_path={gpio_path} - e={e}')

        if os.path.isfile(gpio_direction_path):
            logger.debug(f'echo {direction} > {gpio_direction_path}')
            for _ in range(3):
                while True:
                    try:
                        with open(gpio_direction_path, 'w') as f:
                            f.write(direction)
                            f.flush()
                    except PermissionError as e:
                        logger.error(f'gpio_direction_path={gpio_direction_path} - e={e}')
                    else:
                        break
        else:
            logger.warning(f'path does not exist - gpio_direction_path={gpio_direction_path}')

        if value is not None:
            if os.path.isfile(gpio_value_path):
                if self.relay_type == self.ACTIVE_LOW:
                    if value == 1:
                        value = 0
                    else:
                        value = 1
                logger.debug(f'echo {value} > {gpio_value_path}')
                for _ in range(3):
                    while True:
                        try:
                            with open(gpio_value_path, 'w') as f:
                                f.write(f'{value}')
                                f.flush()
                        except PermissionError as e:
                            logger.error(f'gpio_value_path={gpio_value_path} - e={e}')
                        else:
                            break
            else:
                logger.warning(f'path does not exist - gpio_value_path={gpio_value_path}')

        if edge is not None:
            if os.path.isfile(gpio_edge_path):
                logger.debug(f'echo {edge} > {gpio_edge_path}')
                for _ in range(3):
                    while True:
                        try:
                            with open(gpio_edge_path, 'w') as f:
                                f.write(f'{edge}')
                                f.flush()
                        except PermissionError as e:
                            logger.error(f'gpio_edge_path={gpio_edge_path} - e={e}')
                        else:
                            break
            else:
                logger.warning(f'path does not exist - gpio_edge_path={gpio_edge_path}')


class Pump(Gpio):
    MAX_DURATION = 600

    TIMED_OUT = 2  # Ran over duration.

    HOURLY = 0.04167
    THREE_HOURLY = 0.125
    DAILY = 1.0
    WEEKLY = 7.0
    MONTHLY = 30.0

    SCHEDULED_RUN_DEFAULT_DURATION = 60
    SCHEDULED_RUN_FREQUENCY_CHOICES = (
        (HOURLY, 'Hourly'),
        (THREE_HOURLY, '3-Hourly'),
        (DAILY, 'Daily'),
        (WEEKLY, 'Weekly'),
        (MONTHLY, 'Monthly'),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    gpio_export_num = models.PositiveSmallIntegerField(help_text='GPIO export number connected to this pump.')
    is_active = models.BooleanField(default=True)
    max_duration = models.PositiveSmallIntegerField(default=MAX_DURATION, help_text='Max. duration in seconds per run.')
    scheduled_run_default_duration = models.FloatField(
        default=SCHEDULED_RUN_DEFAULT_DURATION, help_text='Default scheduled runtime duration in seconds.')
    scheduled_run_frequency = models.FloatField(
        blank=True, null=True, choices=SCHEDULED_RUN_FREQUENCY_CHOICES, default=DAILY, help_text='In days.')
    scheduled_run_email_notification_recipients = ArrayField(models.EmailField(), blank=True, null=True)

    def __str__(self):
        return '<%s device=%s gpio_export_num=%d>' % (self.__class__.__name__, self.device, self.gpio_export_num)

    def __repr__(self):
        return str(self)

    class Meta:
        ordering = ('gpio_export_num', )

    @property
    def name(self):
        return f'{self.device.name} #{self.gpio_export_num}'

    @property
    def redis_key(self):
        return f'{settings.REDIS_KEY_PREFIX}:pump:{self.id}:{self.ON}'

    @property
    def status(self):
        """Returns pump status based on latest run state."""
        try:
            run = self.run_set.select_related('scheduled_run').latest('start_time')
        except Run.DoesNotExist:
            return self.OFF
        else:
            if run.end_time is not None:
                return self.OFF
            duration = self.max_duration
            if run.scheduled_run is not None:
                duration = run.scheduled_run.duration
            if (timezone.now() - run.start_time).total_seconds() > duration:
                return self.TIMED_OUT
            return self.ON

    @staticmethod
    def parse_redis_pubsub_msg(msg):
        msg_type = msg['type']
        msg_channel = msg['channel']
        msg_data = msg['data']
        logger.info(f'msg_type={msg_type} - msg_channel={msg_channel} - msg_data={msg_data}')

        if msg_type != 'pmessage':
            return (None, None)

        # msg_channel example: '__keyspace@0__:gardener:pump:1:1'
        msg_channel = msg_channel.decode()
        if f'{settings.REDIS_KEY_PREFIX}:pump:' not in msg_channel:
            return (None, None)

        pump_id = int(msg_channel.split('@')[1].split(':')[3])
        pump_status = None

        msg_data = msg_data.decode()
        if msg_data == 'set':
            pump_status = Pump.ON
        elif msg_data in ('del', 'expired'):
            pump_status = Pump.OFF

        return (pump_id, pump_status)

    def start(self, scheduled_run=None):
        if self.status in (self.ON, self.TIMED_OUT):
            logger.warning('pump is already started')
            return None
        if scheduled_run is not None:
            run = Run.objects.create(pump=self, start_time=timezone.now(), scheduled_run=scheduled_run)
        else:
            run = Run.objects.create(pump=self, start_time=timezone.now())
        settings.REDIS_CONN.set(self.redis_key, 1)
        if scheduled_run is not None:
            ttl = int(scheduled_run.duration * 1000)
            logger.info(f'redis_key={self.redis_key} - ttl={ttl}')
            settings.REDIS_CONN.pexpire(self.redis_key, ttl)
        logger.info(f'pump started - run={run}')
        return run

    def stop(self, force=False):
        if self.status in (self.ON, self.TIMED_OUT):
            try:
                run = self.run_set.filter(end_time__isnull=True).latest('start_time')
            except Run.DoesNotExist as e:
                logger.error(f'e={e}')
                if force:
                    settings.REDIS_CONN.delete(self.redis_key)
                logger.info(f'pump force stopped')
            else:
                run.end_time = timezone.now()
                run.save()
                settings.REDIS_CONN.delete(self.redis_key)
                logger.info(f'pump stopped - run={run}')
        else:
            logger.warning('pump is already stopped')


class PopToPumpDuration(models.Model):
    """Model to set desired duration per pump runtime given probability of precipitation."""
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE)
    pop = models.PositiveSmallIntegerField(verbose_name='POP', help_text='Probability of precipitation in %.')
    duration = models.FloatField(help_text='Runtime duration in seconds.')

    def __str__(self):
        return '<%s pump=%s pop=%d duration=%f>' % (self.__class__.__name__, self.pump, self.pop, self.duration)

    def __repr__(self):
        return str(self)

    class Meta:
        verbose_name = 'POP to pump duration'


class ScheduledRun(models.Model):
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE)
    weather_forecast = models.ForeignKey(WeatherForecast, blank=True, null=True, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    duration = models.FloatField(help_text='Runtime duration in seconds.')

    def __str__(self):
        return '<%s id=%d pump=%s start_time=%s duration=%f>' % (
            self.__class__.__name__, self.id, self.pump, self.start_time, self.duration)

    def __repr__(self):
        return str(self)


class Run(models.Model):
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    scheduled_run = models.ForeignKey(ScheduledRun, blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return '<%s id=%d pump=%s start_time=%s end_time=%s>' % (
            self.__class__.__name__, self.id, self.pump, self.start_time, self.end_time)

    def __repr__(self):
        return str(self)


class Lcd(Gpio):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    pump = models.ForeignKey(Pump, blank=True, null=True, on_delete=models.CASCADE)
    sw1_gpio_export_num = models.PositiveSmallIntegerField(
        help_text='GPIO export number for switch 1.', blank=True, null=True)
    sw2_gpio_export_num = models.PositiveSmallIntegerField(
        help_text='GPIO export number for switch 2.', blank=True, null=True)
    led_gpio_export_nums = ArrayField(models.PositiveSmallIntegerField(), blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return '<%s device=%s pump=%s>' % (self.__class__.__name__, self.device, self.pump)

    class Meta:
        verbose_name = 'LCD'
        verbose_name_plural = 'LCDs'

    def init_interrups(self):
        self.set_gpio_value(self.sw1_gpio_export_num, None, direction=self.IN, edge=self.FALLING)
        self.set_gpio_value(self.sw2_gpio_export_num, None, direction=self.IN, edge=self.FALLING)

    def init_leds(self, value=Gpio.OFF):
        for gpio_export_num in self.led_gpio_export_nums:
            self.set_gpio_value(gpio_export_num, value)

    def set_leds(self, leds):
        self.init_leds()
        for gpio_export_num in self.led_gpio_export_nums[:leds]:
            self.set_gpio_value(gpio_export_num, Gpio.ON)

    def run(self):
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        threads = []

        if self.sw1_gpio_export_num and self.sw2_gpio_export_num:
            self.init_interrups()
            thread = InterruptHandlerThread(
                ((self.sw1_gpio_export_num, self.sw1_callback), (self.sw2_gpio_export_num, self.sw2_callback)))
            threads.append(thread)

        if self.led_gpio_export_nums:
            self.init_leds()
            thread = PollingThread(3600, self.pop_monitor_callback)
            threads.append(thread)

        thread = PollingThread(3600, self.lcd_text_callback)
        threads.append(thread)

        try:
            for thread in threads:
                thread.start()
            signal.pause()
        except SignalException:
            logger.info(f'terminating threads')
            for thread in threads:
                thread.terminating.set()
                thread.join(timeout=5)

    def signal_handler(self, signum, frame):
        logger.info(f'caught signum={signum}')
        raise SignalException

    def sw1_callback(self):
        self.pump.start()

    def sw2_callback(self):
        self.pump.stop()

    def pop_monitor_callback(self):
        weather_forecast = self.device.weather_forecasts.order_by('delta').first()
        if weather_forecast:
            pop = weather_forecast.pop
            leds = int(pop / (100 / len(self.led_gpio_export_nums)))
            logger.info(f'pop={pop} - leds={leds}')
            self.set_leds(leds)

    def lcd_text_callback(self):
        private_ip = get_private_ip()
        public_ip = get_public_ip()

        with open(settings.LCD_TEXT_PATH, 'w') as f:
            l1_chars = f.write(f'{private_ip}\n')
            logger.info(f'l1_chars={l1_chars}')

            l2_chars = f.write(f'{public_ip}\n')
            logger.info(f'l2_chars={l2_chars}')


class Camera(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    index = models.PositiveSmallIntegerField(default=0, help_text='Camera index passed to cv2.')
    width = models.PositiveSmallIntegerField(default=1280, help_text='Camera frame width passed to cv2.')
    height = models.PositiveSmallIntegerField(default=960, help_text='Camera frame height passed to cv2.')

    snapshot_extension = models.CharField(max_length=3, default='jpg')
    snapshot_frequency = models.PositiveIntegerField(default=3600, help_text='In seconds.')
    snapshot_duration = models.PositiveIntegerField(default=0)
    current_snapshot = models.PositiveIntegerField(default=0)
    max_snapshots = models.PositiveIntegerField(default=100)

    def __str__(self):
        return '<%s device=%s index=%d>' % (self.__class__.__name__, self.device, self.index)

    @property
    def snapshots_dir(self):
        return os.path.join(settings.MEDIA_ROOT, 'snapshots', str(self.device.id), str(self.id))

    @property
    def snapshots_url(self):
        return os.path.join(settings.MEDIA_URL, 'snapshots', str(self.device.id), str(self.id))


class Light(Gpio):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    gpio_export_num = models.PositiveSmallIntegerField(help_text='GPIO export number connected to this light.')
    is_active = models.BooleanField(default=True)
    start_time = models.TimeField()
    duration = models.FloatField(help_text='Runtime duration in seconds.')

    def __str__(self):
        return '<%s device=%s gpio_export_num=%d>' % (self.__class__.__name__, self.device, self.gpio_export_num)

    def __repr__(self):
        return str(self)

    def start(self):
        if self.gpio_value(self.gpio_export_num) != self.ON:
            logger.info(f'starting light={self}')
            self.set_gpio_value(self.gpio_export_num, self.ON)

    def stop(self):
        if self.gpio_value(self.gpio_export_num) != self.OFF:
            logger.info(f'stopping light={self}')
            self.set_gpio_value(self.gpio_export_num, self.OFF)
