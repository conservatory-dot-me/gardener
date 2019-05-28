from django.db import models


class WeatherForecastProvider(models.Model):
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=200, unique=True)
    url = models.URLField(blank=True)

    def __str__(self):
        return '<%s name=%s url=%s>' % (self.__class__.__name__, self.name, self.url)

    def __repr__(self):
        return str(self)


class Location(models.Model):
    name = models.CharField(max_length=200, unique=True)
    weather_forecast_provider = models.ForeignKey(WeatherForecastProvider, on_delete=models.CASCADE)

    def __str__(self):
        return '<%s name=%s>' % (self.__class__.__name__, self.name)

    def __repr__(self):
        return str(self)


class WeatherForecast(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    temp_unit = models.CharField(max_length=2, default='°C')
    min_temp = models.PositiveSmallIntegerField(blank=True, null=True)
    max_temp = models.PositiveSmallIntegerField(blank=True, null=True)
    pop = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name='POP', help_text='Probability of precipitation in %.')

    def __str__(self):
        return '<%s location=%s start_time=%s pop=%s>' % (
            self.__class__.__name__, self.location, self.start_time, self.pop)

    def __repr__(self):
        return str(self)

    class Meta:
        ordering = ('-start_time', )
