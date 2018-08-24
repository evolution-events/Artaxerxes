from django.conf.urls import url

from . import views

app_name = 'events'
urlpatterns = [
    url(r'^$', views.event_index_view, name='index'),
    url(r'/list/', views.event_list_view, name='eventlist'),
]
