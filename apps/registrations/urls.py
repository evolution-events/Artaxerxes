from django.conf.urls import url

from . import views

app_name = 'registrations'
urlpatterns = [
    url(r'r/(?P<eventid>[0-9]+)/', views.RegistrationStartView.as_view(), name="prepare_registration"),
    url(r'r/pd/(?P<registrationid>[0-9]+)/', views.registration_step_personal_details, name="personaldetailform"),
    url(r'r/md/(?P<registrationid>[0-9]+)/', views.registration_step_medical_details, name="medicaldetailform"),
    url(r'r/op/(?P<registrationid>[0-9]+)/', views.registration_step_options, name="optionsform"),
    url(r'r/fc/(?P<registrationid>[0-9]+)/', views.registration_step_final_check, name="finalcheckform"),
]
