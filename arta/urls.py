"""Artaxerxes URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
from django.contrib import admin
from django.conf.urls import url, include
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

    url(r'^people/', include('apps.people.urls')),  # include urls of the people app
    url(r'^events/', include('apps.events.urls')),  # include urls of the events app
]
