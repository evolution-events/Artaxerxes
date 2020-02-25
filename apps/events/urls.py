from django.urls import path

from . import views

app_name = 'events'
urlpatterns = [
    path('list/', views.event_list_view, name='eventlist'),
]
