from django.contrib import admin

from gardener.device.models import Camera
from gardener.device.models import Device
from gardener.device.models import Fan
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
        'scheduled_run_email_notification_recipients',
    )


class CameraInline(admin.TabularInline):
    model = Camera
    extra = 0
    fields = (
        'is_active',
        'index',
        'width',
        'height',
        'snapshot_extension',
        'snapshot_frequency',
        'snapshot_duration',
        'current_snapshot',
        'max_snapshots',
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


class FanInline(admin.TabularInline):
    model = Fan
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
        CameraInline,
        LightInline,
        FanInline,
    )


class PumpAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'gpio_export_num',
        'is_active',
        'max_duration',
        'scheduled_run_default_duration',
        'scheduled_run_frequency',
        'scheduled_run_email_notification_recipients',
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
    readonly_fields = (
        'weather_forecast',
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
        'width',
        'height',
        'snapshot_extension',
        'snapshot_frequency',
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


class FanAdmin(admin.ModelAdmin):
    list_display = (
        'device',
        'gpio_export_num',
        'is_active',
        'start_time',
        'duration',
    )


admin.site.register(Camera, CameraAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(Fan, FanAdmin)
admin.site.register(Lcd, LcdAdmin)
admin.site.register(Light, LightAdmin)
admin.site.register(PopToPumpDuration, PopToPumpDurationAdmin)
admin.site.register(Pump, PumpAdmin)
admin.site.register(Run, RunAdmin)
admin.site.register(ScheduledRun, ScheduledRunAdmin)
