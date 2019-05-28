from django.contrib import admin

from gardener.data.models import Location
from gardener.data.models import WeatherForecast
from gardener.data.models import WeatherForecastProvider


class WeatherForecastProviderAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'url',
    )


class LocationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'weather_forecast_provider',
    )


class WeatherForecastAdmin(admin.ModelAdmin):
    list_display = (
        'location',
        'start_time',
        'end_time',
        'temp_unit',
        'min_temp',
        'max_temp',
        'pop',
    )


admin.site.register(Location, LocationAdmin)
admin.site.register(WeatherForecast, WeatherForecastAdmin)
admin.site.register(WeatherForecastProvider, WeatherForecastProviderAdmin)
