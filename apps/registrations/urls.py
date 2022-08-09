from django.urls import path

from . import views

app_name = 'registrations'
urlpatterns = [
    path('<int:eventid>/', views.RegistrationStart.as_view(), name="registration_start"),
    path('es/<int:eventid>/', views.EditStart.as_view(), name="edit_start"),
    path('pd/<int:pk>/', views.PersonalDetailsStep.as_view(), name="step_personal_details"),
    path('md/<int:pk>/', views.MedicalDetailsStep.as_view(), name="step_medical_details"),
    path('ec/<int:pk>/', views.EmergencyContactsStep.as_view(), name="step_emergency_contacts"),
    path('op/<int:pk>/', views.RegistrationOptionsStep.as_view(), name="step_registration_options"),
    path('fc/<int:pk>/', views.FinalCheck.as_view(), name="step_final_check"),
    path('rc/<int:pk>/', views.RegistrationConfirmation.as_view(), name="registration_confirmation"),
    path('cr/<int:pk>/', views.ConflictingRegistrations.as_view(), name="conflicting_registrations"),
    path('ps/<int:pk>/', views.PaymentStatus.as_view(), name="payment_status"),
    path('pc/<int:pk>/', views.PaymentDone.as_view(), name="payment_done"),
    path('ed/<int:pk>/', views.EditDone.as_view(), name="edit_done"),
]
