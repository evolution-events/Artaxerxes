from django.urls import path

from . import views

app_name = 'registrations'
urlpatterns = [
    path('<int:eventid>/', views.RegistrationStartView.as_view(), name="register"),
    path('registration/<int:pk>/', views.RegistrationDetailView.as_view(), name="registration_detail"),
    path('pd/<int:registrationid>/', views.registration_step_personal_details, name="personaldetailform"),
    path('md/<int:registrationid>/', views.registration_step_medical_details, name="medicaldetailform"),
    path('op/<int:registrationid>/', views.registration_step_options, name="optionsform"),
    path('fc/<int:registrationid>/', views.registration_step_final_check, name="finalcheckform"),
]
