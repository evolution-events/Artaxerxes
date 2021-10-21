from django.urls import path

from . import views

app_name = 'payments'
urlpatterns = [
    path('webhook/<int:pk>', views.PaymentChanged.as_view(), name='webhook'),
]
