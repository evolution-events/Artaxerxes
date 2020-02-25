from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('', views.RegistrationsDashboardView.as_view(), name='main_index_view'),
    path('practical_info', views.practical_info_view, name='practical_info_view'),
]
