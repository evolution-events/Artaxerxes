from django.urls import path

from . import views

app_name = 'events'
urlpatterns = [
    path('registered/', views.RegisteredEventList.as_view(), name='registered_events'),
    path('organized/', views.OrganizedEventsList.as_view(), name='organized_events'),
    path('organized/<int:pk>/forms/print', views.PrintableRegistrationForms.as_view(),
         name='printable_registration_forms'),
    path('organized/<int:pk>/forms', views.RegistrationForms.as_view(), name='registration_forms'),
    path('organized/<int:pk>/kitchen_info/print', views.PrintableKitchenInfo.as_view(), name='printable_kitchen_info'),
    path('organized/<int:pk>/kitchen_info', views.KitchenInfo.as_view(), name='kitchen_info'),
    path('organized/<int:pk>/safety_reference/print', views.PrintableSafetyReference.as_view(),
         name='printable_safety_reference'),
    path('organized/<int:pk>/safety_reference', views.SafetyReference.as_view(), name='safety_reference'),
    path('organized/<int:pk>/safety_info', views.SafetyInfo.as_view(), name='safety_info'),
    path('organized/<int:pk>/registrations', views.RegistrationsTable.as_view(), name='registrations_table'),
    path('organized/<int:pk>/registrations/download', views.RegistrationsTableDownload.as_view(),
         name='registrations_table_download'),
    path('organized/<int:pk>/history', views.EventRegistrationsHistory.as_view(), name='event_registrations_history'),
]
