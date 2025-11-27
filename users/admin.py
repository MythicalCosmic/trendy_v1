from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.sites import UnfoldAdminSite

# Replace the default admin site header
admin.site.__class__ = UnfoldAdminSite