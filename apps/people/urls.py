from django.conf.urls import url
from django.views.i18n import JavaScriptCatalog

from . import views

app_name = 'people'
urlpatterns = [
        url(r'^$', views.person_index_view, name='index'),  # Entrance page for the people app
]