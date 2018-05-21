"""Artaxerxes URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
from django.contrib import admin
# Django imports
from django.conf.urls import url, include
from django.contrib.auth import views as auth_views

from apps.people import views as people_views

urlpatterns = [
    # Examples:
    # url(r'^blog/', include('blog.urls', namespace='blog')),

    # provide the most basic login/logout functionality
    url(r'^login/$', auth_views.login,
        {'template_name': 'core/login.html'}, name='core_login'),
    url(r'^logout/$', auth_views.logout, name='core_logout'),

    # enable the admin interface
    url(r'^admin/', admin.site.urls),

    # url to the welcome page
    url(r'^$', people_views.main_index_view, name='main_index_view'),

    url(r'^people/', include('apps.people.urls')),  # include urls of the people app
    url(r'^events/', include('apps.events.urls')),  # include urls of the events app
]
