import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.http.response import Http404

from gardener.device.models import Device
from gardener.device.models import Pump
from gardener.utils import datetime_to_unixtimestamp

logger = logging.getLogger('gardener')


@api_view(['POST'])
def start_pump(request, pump_id):
    logger.info(f'starting pump - pump_id={pump_id}')
    try:
        pump = Pump.objects.filter(device__is_active=True, is_active=True).get(id=pump_id)
    except Pump.DoesNotExist as e:
        logger.warning(f'e={e}')
        raise Http404
    else:
        pump.start()
    return Response(dict(id=pump.id))


@api_view(['POST'])
def stop_pump(request, pump_id):
    logger.info(f'stopping pump - pump_id={pump_id}')
    try:
        pump = Pump.objects.get(id=pump_id)
    except Pump.DoesNotExist as e:
        logger.warning(f'e={e}')
        raise Http404
    else:
        pump.stop()
    return Response(dict(id=pump.id))


@api_view(['GET'])
def weather_forecasts(request, device_id):
    forecasts = []
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist as e:
        logger.warning(f'e={e}')
        raise Http404
    else:
        for f in device.weather_forecasts:
            forecasts.append((datetime_to_unixtimestamp(f.start_time), f.temp_unit, f.min_temp, f.max_temp, f.pop))
    return Response(forecasts)
