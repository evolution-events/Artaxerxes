from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import View

from apps.people.models import Address, MedicalDetails


class PersonDetailsView(LoginRequiredMixin, View):
    def get(self, request):
        personal_details = Address.objects.filter(user=request.user).first()  # Returns None if nothing was found
        medical_details = MedicalDetails.objects.filter(user=request.user).first()  # Returns None if nothing was found
        context = {
            'user': request.user,
            'pdetails': personal_details,
            'mdetails': medical_details,
        }
        return render(request, 'people/index.html', context)
