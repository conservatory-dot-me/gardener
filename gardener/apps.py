from django.contrib.admin.apps import AdminConfig


class GardenerAdminConfig(AdminConfig):
    default_site = 'gardener.admin.GardenerAdminSite'
