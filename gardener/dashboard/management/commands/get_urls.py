from django.core.management import BaseCommand
from django.urls import reverse

from gardener.utils import get_private_ip
from gardener.utils import nginx_configured


class Command(BaseCommand):
    help = 'Print device URLs.'

    def handle(self, *args, **options):
        private_ip = get_private_ip()

        if nginx_configured():
            root_url = f'http://{private_ip}'
        else:
            root_url = f'http://localhost:8000'

        dashboard_path = reverse('dashboard')
        admin_path = reverse('admin:index')
        print(f'Dashboard: {root_url}{dashboard_path}')
        print(f'Admin page: {root_url}{admin_path}')
