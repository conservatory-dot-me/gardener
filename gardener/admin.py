from django.contrib import admin


class GardenerAdminSite(admin.AdminSite):
    site_header = 'Gardener Admin'
    site_title = 'Gardener'
    index_title = 'Gardener Admin'
