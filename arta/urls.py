"""Artaxerxes URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth.decorators import login_required

from apps.people import views as people_views

# Workaround to let the admin site use the regular login form instead of its own, see
# https://django-allauth.readthedocs.io/en/latest/advanced.html#admin
# TODO: This does not work when a user is logged in, but does not have admin site permissions.
admin.site.login = login_required(admin.site.login)


urlpatterns = [
    # Examples:
    # url(r'^blog/', include('blog.urls', namespace='blog')),

    url(r'^accounts/', include('allauth.urls')),

    # enable the admin interface
    url(r'^admin/', admin.site.urls),

    # url to the welcome page
    url(r'^$', people_views.main_index_view, name='main_index_view'),

    # Include urls of the apps
    url(r'^people/', include('apps.people.urls')),
    url(r'^events/', include('apps.events.urls')),
    url(r'^registrations/', include('apps.registrations.urls')),
]
