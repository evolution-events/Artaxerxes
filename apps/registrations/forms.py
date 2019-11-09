from django import forms
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


class RegistrationOptionsForm(forms.Form):
    """ A dynamic form showing registration options for a given event. """

    def __init__(self, event, user, **kwargs):
        """ Create a new form for the given user to register to event. """
        super().__init__(**kwargs)

        self.add_fields(event, user)

    def add_fields(self, event, user):
        """ Add form fields based on the RegistrationFields in the database. """
        groups = user.groups.all()
        for registration_field in event.registration_fields.all():
            if registration_field.invite_only and registration_field.invite_only not in groups:
                continue

            # TODO: Handle depends
            # TODO: Handle allow_change_until

            if registration_field.field_type == RegistrationField.TYPE_CHOICE:
                choices = []
                for option in registration_field.options.all():
                    if option.invite_only and option.invite_only not in groups:
                        continue

                    # TODO: Handle depends
                    # TODO: Handle slots/full
                    title = option.title
                    if option.price is not None:
                        title += " (€{})".format(option.price)
                    choices.append((option.pk, title))
                field = forms.ChoiceField(choices=choices, label=registration_field.title)
            elif registration_field.field_type == RegistrationField.TYPE_STRING:
                field = forms.CharField(label=registration_field.title)
            field.readonly = True
            self.fields[registration_field.name] = field
