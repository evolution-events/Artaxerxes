from django.conf.urls import url
from django.views.i18n import JavaScriptCatalog

from . import views

app_name = 'events'
urlpatterns = [
        url(r'^$', views.event_index_view, name='index'),
]