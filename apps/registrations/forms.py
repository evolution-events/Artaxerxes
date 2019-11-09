from django import forms
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.people.models import Address, MedicalDetails
from apps.registrations.models import RegistrationField

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


class RegistrationOptionField(forms.ModelChoiceField):
    """ Field that allows selecting from multiple options, including price and status info. """

    def label_from_instance(self, obj):
        label = obj.title
        if obj.price is not None:
            label += " (€{})".format(obj.price)
        if obj.full:
            label += " FULL"
        return label


class RegistrationOptionsForm(forms.Form):
    """ A dynamic form showing registration options for a given event. """

    def __init__(self, event, user, **kwargs):
        """ Create a new form for the given user to register to event. """
        super().__init__(**kwargs)

        self.event = event
        self.user = user
        self.add_fields()

    def add_fields(self):
        """ Add form fields based on the RegistrationFields in the database. """
        fields = self.event.registration_fields.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
        for field in fields:
            # TODO: Handle depends
            # TODO: Handle allow_change_until

            if field.field_type == RegistrationField.TYPE_CHOICE:
                # TODO: Handle depends
                options = field.options.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
                form_field = RegistrationOptionField(queryset=options, label=field.title, empty_label=None)
            elif field.field_type == RegistrationField.TYPE_STRING:
                form_field = forms.CharField(label=field.title)
            form_field.readonly = True
            self.fields[field.name] = form_field
