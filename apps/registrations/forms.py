from django import forms
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.people.models import Address, MedicalDetails
from apps.registrations.models import RegistrationField, RegistrationFieldValue

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

    def __init__(self, event, user, registration=None, **kwargs):
        """ Create a new form for the given user to register to event. """

        if registration:
            kwargs['initial'] = self.values_for_registration(registration)

        super().__init__(**kwargs)

        self.event = event
        self.user = user
        self.add_fields()

    def values_for_registration(self, registration):
        values = {}
        for option in registration.options.all():
            if option.field.field_type == RegistrationField.TYPE_CHOICE:
                value = option.option
            else:
                value = option.string_value

            values[option.field.name] = value
        return values

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

    def add_error_by_code(self, field_name, code, **kwargs):
        # Add an error for the given field, reusing the predefined error messages for that field.
        field = self.fields[field_name]
        msg = field.error_messages[code]
        self.add_error(field_name, forms.ValidationError(msg, code=code, values=kwargs))

    def clean(self):
        # Most validation is implicit based on the generated form (e.g. based on required, choices, etc.)
        super().clean()
        d = self.cleaned_data

        fields = self.event.registration_fields.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
        for field in fields:
            # If the dependencies for this option are not satisfied, ignore it
            if field.depends and d.get(field.depends.field.name, None) != field.depends:
                continue

            if field.field_type == RegistrationField.TYPE_CHOICE:
                try:
                    option = d[field.name]
                except KeyError:
                    self.add_error_by_code(field.name, 'required')
                else:
                    if option.depends and d.get(option.depends.field.name, None) != option.depends:
                        self.add_error_by_code(field.name, 'invalid_choice', value=option.title)

    def save(self, registration):
        d = self.cleaned_data

        fields = self.event.registration_fields.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
        for field in fields:
            # If the dependencies for this option are not satisfied, delete any values for it that might be present
            if field.depends and d.get(field.depends.field.name, None) != field.depends:
                RegistrationFieldValue.objects.filter(registration=registration, field=field).delete()
                continue

            (value, created) = RegistrationFieldValue.objects.get_or_create(registration=registration, field=field)
            if field.field_type == RegistrationField.TYPE_CHOICE:
                value.option = d[field.name]
            else:
                value.string_value = d[field.name]
            value.save()

            # TODO: Handle allow_change_until
