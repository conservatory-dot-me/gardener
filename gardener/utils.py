import calendar
import ephem
import logging
import os
import pytz
import requests
import select
import socket
import threading
import time
from datetime import datetime
from psutil import net_if_addrs
from timezonefinder import TimezoneFinder
from urllib.request import urlretrieve

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mass_mail
from django.utils import timezone

logger = logging.getLogger('gardener')


class InterruptHandlerThread(threading.Thread):
    def __init__(self, tuples, **kwargs):
        super().__init__(**kwargs)
        self.terminating = threading.Event()
        self.tuples = tuples
        self.warmup_time = 3  # Ignore triggers during the first 3 seconds.

    def run(self):
        values = [f'/sys/class/gpio/gpio{gpio_export_num}/value' for (gpio_export_num, _) in self.tuples]
        files = [open(value) for value in values]
        logger.info(f'{self.__class__.__name__} started - ident={self.ident}')

        start_time = time.time()

        epoll = select.epoll()
        for file in files:
            epoll.register(file, select.EPOLLIN | select.EPOLLET)

        while not self.terminating.is_set():
            events = epoll.poll(timeout=1)
            for fileno, event in events:
                for index, file in enumerate(files):
                    if fileno == file.fileno() and time.time() - start_time > self.warmup_time:
                        self.tuples[index][1]()  # Invoke callback method.

        for file in files:
            file.close()
        logger.info(f'{self.__class__.__name__} terminated - ident={self.ident}')


class PollingThread(threading.Thread):
    def __init__(self, seconds, callback, **kwargs):
        super().__init__(**kwargs)
        self.terminating = threading.Event()
        self.seconds = seconds
        self.callback = callback

    def run(self):
        logger.info(f'{self.__class__.__name__} started - ident={self.ident}')

        last_run = None
        while not self.terminating.is_set():
            now = time.time()
            if last_run is None or now - last_run > self.seconds:
                self.callback()
                last_run = now
            time.sleep(1)

        logger.info(f'{self.__class__.__name__} terminated - ident={self.ident}')


class EmailThread(threading.Thread):
    def __init__(self, datatuple, **kwargs):
        self.datatuple = datatuple
        super().__init__(**kwargs)

    def run(self):
        sent = send_mass_mail(self.datatuple, fail_silently=True)
        logger.info(f'datatuple={self.datatuple} - sent={sent}')


def ftp_get(url):
    logger.info(f'url={url}')
    content = ''
    (filename, headers) = urlretrieve(url)
    with open(filename) as f:
        content = f.read()
    os.remove(filename)
    return content


def http_get(url, headers=None, params=None, timeout=5):
    logger.info(f'url={url}')
    while True:
        logger.debug(f'url={url} - headers={headers} - params={params}')
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.RequestException as err:
            logger.warning(f'err={err}')
            logger.info(f'sleeping for {timeout}s before retrying')
            time.sleep(timeout)
        else:
            break
    return response


def get_private_ip():
    private_ip = cache.get('private_ip')
    if private_ip is None:
        for interface in net_if_addrs().keys():
            if interface.startswith(('eth', 'wlan', 'en')):
                for address in net_if_addrs().get(interface):
                    if address.family == socket.AF_INET:
                        private_ip = address.address
                        logger.info(f'private_ip={private_ip}')
                        cache.set('private_ip', private_ip, timeout=3600)
                        return private_ip
    return private_ip


def get_public_ip():
    url = 'https://dazzlepod.com/ip/me.json'
    public_ip = cache.get('public_ip')
    if public_ip is None:
        response = http_get(url)
        public_ip = response.json()['ip']
        logger.info(f'public_ip={public_ip}')
        cache.set('public_ip', public_ip, timeout=3600)
    return public_ip


def nginx_configured():
    if os.path.exists(os.path.join(settings.BASE_DIR, 'nginx.conf')):
        return True
    return False


def get_next_sun(lat, lon, date=None):
    """Returns a tuple of next sunrise and sunset given the specified latitude and longitude."""
    if date is None:
        date = timezone.now()

    loc = ephem.Observer()
    loc.date = date
    loc.lat = str(lat)
    loc.lon = str(lon)
    loc.elev = 0
    loc.horizon = '-0:34'
    loc.pressure = 0

    dt = loc.next_rising(ephem.Sun(), use_center=False).datetime()
    next_sunrise = timezone.make_aware(dt, pytz.timezone('UTC'))

    dt = loc.next_setting(ephem.Sun(), use_center=False).datetime()
    next_sunset = timezone.make_aware(dt, pytz.timezone('UTC'))

    logger.debug(
        f'lat={lat} - lon={lon} - date={date} - '
        f'next_sunrise={timezone.localtime(next_sunrise)} - next_sunset={timezone.localtime(next_sunset)}')

    return next_sunrise, next_sunset


def get_time_zone(latitude, longitude):
    """Returns time zone for the specified location."""
    return TimezoneFinder().timezone_at(lat=latitude, lng=longitude)


def get_local_time(latitude, longitude):
    """Returns local time for the specified location."""
    local_tz = pytz.timezone(get_time_zone(latitude, longitude))
    return timezone.now().astimezone(local_tz)


def datetime_to_unixtimestamp(dt):
    return calendar.timegm(dt.timetuple())


def unixtimestamp_to_datetime(timestamp):
    return timezone.localtime(datetime.fromtimestamp(timestamp, tz=pytz.UTC))


def time_in_range(start_time, end_time, now):
    if start_time <= end_time:
        return start_time <= now <= end_time
    else:
        return now >= start_time or now <= end_time


def send_email_notification(subject, message):
    subject = f'{settings.EMAIL_SUBJECT_PREFIX}{subject}'
    datatuple = []
    for recipient in settings.EMAIL_NOTIFICATION_RECIPIENTS:
        datatuple.append((subject, message, None, (recipient, )))
    if datatuple:
        EmailThread(datatuple).start()
