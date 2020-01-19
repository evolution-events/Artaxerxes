from django.urls import path

from . import views

app_name = 'people'
urlpatterns = [
    path('', views.PersonDetailsView.as_view(), name='index'),  # Entrance page for the people app
]
