from django.contrib import admin

from gardener.device.models import Camera
from gardener.device.models import Device
from gardener.device.models import Lcd
from gardener.device.models import Light
from gardener.device.models import PopToPumpDuration
from gardener.device.models import Pump
from gardener.device.models import Run
from gardener.device.models import ScheduledRun


class PumpInline(admin.TabularInline):
    model = Pump
    extra = 1

    fields = (
        'gpio_export_num',
        'is_active',
        'max_duration',
        'scheduled_run_default_duration',
        'scheduled_run_frequency',
    )


class LightInline(admin.TabularInline):
    model = Light
    extra = 1

    fields = (
        'gpio_export_num',
        'is_active',
        'start_time',
        'duration',
    )


class PopToPumpDurationInline(admin.TabularInline):
    model = PopToPumpDuration
    extra = 1

    fields = (
        'pop',
        'duration',
    )


class RunInline(admin.TabularInline):
    model = Run
    can_delete = False
    extra = 0

    fields = (
        'id',
        'pump',
        'start_time',
        'end_time',
    )

    readonly_fields = fields

    def has_add_permission(self, *args, **kwargs):
        return False


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'location',
        'latitude',
        'longitude',
    )
    inlines = (
        PumpInline,
        LightInline,
    )


class PumpAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'gpio_export_num',
        'is_active',
        'max_duration',
        'scheduled_run_default_duration',
        'scheduled_run_frequency',
    )
    inlines = (
        PopToPumpDurationInline,
    )


class PopToPumpDurationAdmin(admin.ModelAdmin):
    list_display = (
        'pump',
        'pop',
        'duration',
    )


class RunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'pump',
        'start_time',
        'end_time',
        'scheduled_run',
    )
    readonly_fields = list_display

    def has_add_permission(self, *args, **kwargs):
        return False


class ScheduledRunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'pump',
        'weather_forecast',
        'start_time',
        'duration',
    )
    inlines = (
        RunInline,
    )


class LcdAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'pump',
        'sw1_gpio_export_num',
        'sw2_gpio_export_num',
        'led_gpio_export_nums',
        'is_active',
    )


class CameraAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'is_active',
        'index',
        'snapshot_extension',
        'snapshot_duration',
        'current_snapshot',
        'max_snapshots',
    )


class LightAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'gpio_export_num',
        'is_active',
        'start_time',
        'duration',
    )


admin.site.register(Device, DeviceAdmin)
admin.site.register(PopToPumpDuration, PopToPumpDurationAdmin)
admin.site.register(Pump, PumpAdmin)
admin.site.register(Run, RunAdmin)
admin.site.register(ScheduledRun, ScheduledRunAdmin)
admin.site.register(Lcd, LcdAdmin)
admin.site.register(Camera, CameraAdmin)
admin.site.register(Light, LightAdmin)
