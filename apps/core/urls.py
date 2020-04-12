from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('', views.RegistrationsDashboardView.as_view(), name='main_index_view'),
    path('practical_info', views.practical_info_view, name='practical_info_view'),
    path('about_this_system', views.AboutArtaView.as_view(), name='about_arta_view'),
    path('privacy', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('rules', views.HouseRulesView.as_view(), name='house_rules'),
]
