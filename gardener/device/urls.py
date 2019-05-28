from django.urls import path

from . import views

urlpatterns = [
    path('weather-forecasts/<device_id>/', views.weather_forecasts, name='weather-forecasts'),
    path('start-pump/<pump_id>/', views.start_pump, name='start-pump'),
    path('stop-pump/<pump_id>/', views.stop_pump, name='stop-pump'),
]
