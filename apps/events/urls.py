from django.urls import path

from . import views

app_name = 'events'
urlpatterns = [
    path('', views.event_index_view, name='index'),
    path('list/', views.event_list_view, name='eventlist'),
]
