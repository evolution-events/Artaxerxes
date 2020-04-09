from django.urls import path

from . import views

app_name = 'registrations'
urlpatterns = [
    path('<int:eventid>/', views.RegistrationStartView.as_view(), name="register"),
    path('pd/<int:pk>/', views.PersonalDetailsStep.as_view(), name="personaldetailform"),
    path('md/<int:pk>/', views.MedicalDetailsStep.as_view(), name="medicaldetailform"),
    path('ec/<int:pk>/', views.EmergencyContactsStep.as_view(), name="emergencycontactsform"),
    path('op/<int:pk>/', views.RegistrationOptionsStep.as_view(), name="optionsform"),
    path('fc/<int:pk>/', views.FinalCheck.as_view(), name="finalcheckform"),
    path('rc/<int:pk>/', views.RegistrationConfirmationView.as_view(), name="registrationconfirmation"),
]
