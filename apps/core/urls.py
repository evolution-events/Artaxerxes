from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('', views.RegistrationsDashboardView.as_view(), name='main_index_view'),
    path('organisation_info', views.organisation_info_view, name='organisation_info_view'),
]
