from django.urls import path

from . import views

app_name = 'events'
urlpatterns = [
    path('registered/', views.RegisteredEventList.as_view(), name='registered_events'),
]
