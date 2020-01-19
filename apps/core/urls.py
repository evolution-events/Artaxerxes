from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('/organisation_info', views.organisation_info_view, name='organisation_info_view'),
]
