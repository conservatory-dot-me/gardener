import logging

from django.core.management import BaseCommand

from gardener.device.models import Lcd

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Run LCD actions.'

    def handle(self, *args, **options):
        lcd = Lcd.objects.filter(device__is_active=True, is_active=True).first()
        if lcd is None:
            return

        if lcd.pump and lcd.pump.is_active:
            lcd.run()
