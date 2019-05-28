from django.conf import settings

from gardener.utils import nginx_configured


def websocket_server(request):
    if nginx_configured():
        websocket_url = f'ws://{request.get_host()}/ws/'  # Nginx proxy.
    else:
        websocket_url = f'ws://{settings.WEBSOCKET_HOST}:{settings.WEBSOCKET_PORT}'
    return dict(websocket_url=websocket_url)
