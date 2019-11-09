from django import forms
from django.utils.translation import gettext as _

from apps.people.models import Address, MedicalDetails

# from apps.events.models import EventOptions


class PersonalDetailForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['address', 'postalcode', 'city', 'country']


class MedicalDetailForm(forms.ModelForm):
    class Meta:
        model = MedicalDetails
        fields = ['food_allergies', 'event_risks']


class FinalCheckForm(forms.Form):
    agree = forms.BooleanField(label=_('Agree to conditions'), required=True)

    # TODO: is this an object, or freeform Form? Link to conditions should be provided. Here (helptext) or in template?
