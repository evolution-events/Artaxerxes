from django.urls import path

from . import views

app_name = 'events'
urlpatterns = [
    path('registered/', views.event_list_view, name='registered_events'),
]
