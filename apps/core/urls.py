from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('', views.RegistrationsDashboardView.as_view(), name='dashboard'),
    path('practical_info', views.practical_info_view, name='practical_info'),
    path('about_this_system', views.AboutArtaView.as_view(), name='about'),
    path('privacy', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('rules', views.HouseRulesView.as_view(), name='house_rules'),
]
