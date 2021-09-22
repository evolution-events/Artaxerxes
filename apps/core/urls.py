from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('', views.Dashboard.as_view(), name='dashboard'),
    path('practical_info', views.PracticalInfo.as_view(), name='practical_info'),
    path('about_this_system', views.AboutArta.as_view(), name='about'),
    path('privacy', views.PrivacyPolicy.as_view(), name='privacy_policy'),
    path('rules', views.HouseRules.as_view(), name='house_rules'),

    path('email_prefs', views.EmailPreferences.as_view(), name='email_prefs'),
]
