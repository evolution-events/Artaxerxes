from django import forms
from django.db.models import Q
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from apps.core.templatetags.coretags import moneyformat
from apps.people.models import Address, ArtaUser, EmergencyContact, MedicalDetails
from apps.registrations.models import RegistrationField, RegistrationFieldValue

# from apps.events.models import EventOptions


class SpanWidget(forms.Widget):
    """ Renders a value wrapped in a <span> tag. """

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(self.attrs, attrs)
        return mark_safe(u'<span%s >%s</span>' % (
            forms.utils.flatatt(final_attrs), value))


class UserDetailsForm(forms.ModelForm):
    # Override the required attribute for these fields
    first_name = ArtaUser._meta.get_field('first_name').formfield(required=True)
    last_name = ArtaUser._meta.get_field('last_name').formfield(required=True)
    email = forms.CharField(
        disabled=True,
        widget=SpanWidget,
        help_text=_('You can change your e-mailaddress in your account settings'),
    )

    class Meta:
        model = ArtaUser
        fields = ['first_name', 'last_name', 'email']


class PersonalDetailForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['address', 'postalcode', 'city', 'country']


class MedicalDetailForm(forms.ModelForm):
    class Meta:
        model = MedicalDetails
        fields = ['food_allergies', 'event_risks']


class BaseEmergencyContactFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        # Remove the "delete" checkboxes, since we implement this differently
        del form.fields[DELETION_FIELD_NAME]

    def _should_delete_form(self, form):
        # The first min_num forms cannot be deleted. Since we do not have access to the form index, we instead rely on
        # the use_required_attribute set by _construct_form below.
        if form.use_required_attribute:
            return False

        # If all these fields are empty, return True and delete this contact
        fields = ('contact_name',)
        return not any(form.cleaned_data.get(i, False) for i in fields)

    def _construct_form(self, i, **kwargs):
        # By default, use_required_attribute is set to False for all forms in a FormSet, since forms might be extra and
        # can be left empty, or when the delete checkbox is checked, attributes are no longer required.
        # In this case, min_num of forms must always have a value and cannot be deleted, so emit the HTML required
        # attribute for them as well.
        if i < self.min_num:
            kwargs['use_required_attribute'] = True
        return super()._construct_form(i, **kwargs)


EmergencyContactFormSet = forms.inlineformset_factory(
    parent_model=ArtaUser,
    model=EmergencyContact,
    formset=BaseEmergencyContactFormSet,
    fields=('contact_name', 'relation', 'phone_number', 'remarks'),
    min_num=EmergencyContact.MIN_PER_USER,
    max_num=EmergencyContact.MAX_PER_USER,
    extra=EmergencyContact.MAX_PER_USER,
)


class FinalCheckForm(forms.Form):
    agree = forms.BooleanField(label=_('Agree to conditions'), required=True)

    # TODO: is this an object, or freeform Form? Link to conditions should be provided. Here (helptext) or in template?


class RegistrationOptionField(forms.ModelChoiceField):
    """ Field that allows selecting from multiple options, including price and status info. """

    def label_from_instance(self, obj):
        label = obj.title
        if obj.price is not None:
            label += " ({})".format(moneyformat(obj.price))
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
