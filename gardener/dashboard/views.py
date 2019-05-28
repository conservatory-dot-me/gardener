from django.template.response import TemplateResponse
from django.utils import timezone

from gardener.device.models import Device
from gardener.device.models import Run
from gardener.device.models import ScheduledRun


def dashboard(request):
    device = Device.objects.primary_device()

    try:
        last_scheduled_run = Run.objects.filter(scheduled_run__isnull=False).latest('end_time')
    except Run.DoesNotExist:
        last_scheduled_run = None

    try:
        next_scheduled_run = ScheduledRun.objects.filter(start_time__gt=timezone.now()).earliest('start_time')
    except ScheduledRun.DoesNotExist:
        next_scheduled_run = None

    context = dict(device=device, last_scheduled_run=last_scheduled_run, next_scheduled_run=next_scheduled_run)
    return TemplateResponse(request, 'dashboard/dashboard.html', context)
