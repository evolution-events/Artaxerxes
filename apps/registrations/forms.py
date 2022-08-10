from django import forms
from django.db import transaction
from django.db.models import Prefetch, Q
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from apps.core.models import ConsentLog
from apps.core.templatetags.coretags import moneyformat
from apps.people.models import Address, ArtaUser, EmergencyContact, MedicalDetails
from apps.registrations.models import RegistrationField, RegistrationFieldOption, RegistrationFieldValue

# from apps.events.models import EventOptions


class SpanWidget(forms.Widget):
    """ Renders a value wrapped in a <span> tag. """

    def render(self, name, value, attrs=None, renderer=None):
        if hasattr(self, 'choices'):
            for (v, label) in self.choices:
                if v == value:
                    value = label
                    break
            # clear consumed iterator, should be needed only once anyway
            self.choices = None
        elif value is True:
            value = _('Yes')
        elif value is False:
            value = _('No')

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
        help_text=_('You can change your e-mail address in your account settings'),
    )

    class Meta:
        model = ArtaUser
        fields = ['first_name', 'last_name', 'email']


class AddressDetailsForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['phone_number', 'address', 'postalcode', 'city', 'country']


class PersonalDetailForm:
    """ Composite form. """

    def __init__(self, user, address, **kwargs):
        prefix = kwargs.pop('prefix') or ''
        self.user_form = UserDetailsForm(instance=user, prefix=prefix + 'user', **kwargs)
        self.address_form = AddressDetailsForm(instance=address, prefix=prefix + 'address', **kwargs)
        self.forms = (self.user_form, self.address_form)

    def save(self, **kwargs):
        for form in self.forms:
            form.save(**kwargs)

    def is_valid(self):
        return all(form.is_valid() for form in self.forms)

    def has_changed(self):
        return any(form.has_changed() for form in self.forms)


class MedicalDetailForm(forms.ModelForm):
    consent = forms.BooleanField(
        label=_('I consent to the processing of the above information'),
        help_text=_(
            'This applies to any food allergies and medical information '
            'that you have provided, to be processed for the purpose of '
            'your safety when attending our events.'),
        required=False,
    )

    def __init__(self, instance=None, *args, **kwargs):
        # If a MedicalDetails instance already exists, consent must have been given already, so precheck the box
        if instance and instance.pk is not None:
            kwargs['initial'] = kwargs.get('initial', {})
            kwargs['initial']['consent'] = True

        super().__init__(instance=instance, *args, **kwargs)

    # TODO: Only show consent checkbox when data is entered (using javascript), and show it as required then?
    def clean(self):
        # This checks only the model fields specified in meta
        any_information = any(self.cleaned_data.get(name) for name in self._meta.fields)
        if not any_information:
            # If no information is supplied, ignore the consent checkbox
            self.cleaned_data['consent'] = False
        elif not self.cleaned_data.get('consent'):
            self.add_error('consent', 'Consent required when any information is specified')

        return self.cleaned_data

    def save(self, registration, *args, **kwargs):
        # Ensure that MedicalDetails are not created or modified when no ConsentLog could be created.
        with transaction.atomic():
            consented = None
            if self.cleaned_data['consent']:
                if self.has_changed():
                    consented = True
                    obj = super().save()
                    user = obj.user
            else:
                if self.instance and self.instance.pk is not None:
                    consented = False
                    user = self.instance.user
                    self.instance.delete()

            if consented is not None:
                ConsentLog.log_consent(
                    user=user,
                    consent_name='medical_data',
                    value=consented,
                    form_field=self.fields['consent'],
                    registration=registration,
                )

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
    fields=('contact_name', 'phone_number', 'relation', 'remarks'),
    min_num=EmergencyContact.MIN_PER_USER,
    max_num=EmergencyContact.MAX_PER_USER,
    extra=EmergencyContact.MAX_PER_USER,
)


class FinalCheckForm(forms.Form):
    agree = forms.BooleanField(label=_('I have read the house rules and agree to the above conditions'), required=True)


class RegistrationOptionField(forms.ModelChoiceField):
    """ Field that allows selecting from multiple options, including price and status info. """

    def label_from_instance(self, obj):
        label = obj.title
        extras = []
        if obj.price is not None:
            extras.append(moneyformat(obj.price))
        if obj.full:
            extras.append(_("FULL"))
        if extras:
            label = "{} ({})".format(label, ", ".join(extras))
        return label


class RegistrationOptionsForm(forms.Form):
    """ A dynamic form showing registration options for a given event. """

    def __init__(self, event, user, registration, **kwargs):
        """ Create a new form for the given user to register to event. """

        kwargs['initial'] = self.values_for_registration(registration)

        super().__init__(**kwargs)

        # Are we changing the registration (in the sense of "allow_change_until"?
        self.is_change = (registration.status.ACTIVE)
        self.event = event
        self.user = user
        self.registration = registration
        self.add_fields()

    def values_for_registration(self, registration):
        # TODO: The has_changed for this form returns False when only checkboxes (and maybe strings) are present (or
        # added since the form was saved before) and are left at their default, since a missing initial value is
        # treated as False/"" by the Django form fields. Maybe the form should be considered changed always when not
        # all fields have a value?

        values = {}
        for option in registration.active_options:
            if option.field.field_type.CHOICE:
                # TODO: In Django 3.0 this can just be option.option again, see
                # https://code.djangoproject.com/ticket/30014
                value = option.option.pk if option.option else None
            elif option.field.field_type.IMAGE:
                value = option.file_value
            elif option.field.field_type.CHECKBOX or option.field.field_type.UNCHECKBOX:
                value = (option.string_value == RegistrationFieldValue.CHECKBOX_VALUES[True])
            else:
                value = option.string_value

            values[option.field.name] = value
        return values

    @property
    def sections(self):
        # Resolve field names to bound fields, since a template cannot do this
        for (section, fields) in self._sections:
            yield (section, [(field, self[field.name]) for field in fields])

    def add_fields(self):
        """ Add form fields based on the RegistrationFields in the database. """
        fields = self.event.registration_fields.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
        # For each field, also prefetch
        fields = fields.prefetch_related(Prefetch(
            'options',
            queryset=RegistrationFieldOption.objects.filter(Q(invite_only=None) | Q(invite_only__user=self.user)),
            to_attr='available_options',
        ))

        fields = fields.select_related('depends__field')
        self._sections = []

        for field in fields:
            kwargs = {
                'help_text': field.help_text,
                'label': conditional_escape(field.title),
                'required': field.required,
            }

            has_initial = (field.name in self.initial)

            if self.is_change:
                # Make fields that can no longer be changed read-only
                if not field.field_type.SECTION and not field.allow_change:
                    # Except for fields that do not have a value yet, just skip those entirely
                    if not has_initial:
                        continue
                    kwargs['disabled'] = True
                    kwargs['widget'] = SpanWidget
                    kwargs['help_text'] = _('This option can no longer be changed — contact organization if needed')

                # Omit fields that depend on a not-selected option on a field that can no longer be changed, because
                # the javascript that normally handles this cannot know the value of the omitted dependend-on-field.
                # Fields that depend on a selected, but unchangeable option will be shown as normal, because the
                # dependency-handling javascript does not act when the depended-on-field is omitted.
                if field.depends and not field.depends.field.allow_change:
                    depend_value = self.initial.get(field.depends.field.name, None)
                    if depend_value != field.depends.pk:
                        continue

            if field.field_type.CHOICE:
                # TODO: This wraps the prefetched list into something that looks enough like a queryset to satisfy
                # ModelChoiceField. It would be better if a prefetch with to_attr would produce a queryset (with
                # prefetched results) rather than a list, but should be reported as a feature request for Django (as
                # suggested here: https://code.djangoproject.com/ticket/26676#comment:1)
                class FakeQueryset(list):
                    def __init__(self, values, model):
                        super().__init__(values)
                        self._prefetch_related_lookups = True
                        self.model = model

                    def all(self):
                        return self

                    def get(self, pk):
                        for v in self:
                            if v.pk == int(pk):
                                return v
                        raise self.model.DoesNotExist()

                options = FakeQueryset(field.available_options, RegistrationFieldOption)

                empty_label = None if has_initial else _('Select one...')
                form_field = RegistrationOptionField(queryset=options, empty_label=empty_label, **kwargs)
            elif field.field_type.RATING5:
                choices = ((str(n), str(n)) for n in range(1, 6))
                if 'widget' not in kwargs:
                    kwargs['widget'] = forms.RadioSelect

                form_field = forms.ChoiceField(choices=choices, **kwargs)
            elif field.field_type.STRING:
                form_field = forms.CharField(**kwargs)
            elif field.field_type.TEXT:
                if 'widget' not in kwargs:
                    kwargs['widget'] = forms.Textarea
                form_field = forms.CharField(**kwargs)
            elif field.field_type.CHECKBOX:
                form_field = forms.BooleanField(**kwargs)
            elif field.field_type.UNCHECKBOX:
                form_field = forms.BooleanField(initial=True, **kwargs)
            elif field.field_type.IMAGE:
                form_field = forms.ImageField(**kwargs)
            elif field.field_type.SECTION:
                form_field = None
                self._sections.append((field, []))
            else:
                raise ValueError("Unsupported field type")

            if form_field:
                if not self._sections:
                    self._sections.append((None, []))
                self._sections[-1][1].append(field)

                self.fields[field.name] = form_field

    def add_error_by_code(self, field_name, code, **kwargs):
        # Add an error for the given field, reusing the predefined error messages for that field.
        field = self.fields[field_name]
        msg = field.error_messages[code]
        self.add_error(field_name, forms.ValidationError(msg, code=code, params=kwargs))

    def depends_satisfied(self, d, depends):
        if depends is None:
            return True
        return self.depends_satisfied(d, depends.field.depends) and d.get(depends.field.name, None) == depends

    def clean(self):
        # Most validation is implicit based on the generated form (e.g. based on required, choices, etc.)
        super().clean()
        d = self.cleaned_data

        fields = self.event.registration_fields.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
        fields = fields.exclude(field_type=RegistrationField.types.SECTION)
        for field in fields:
            # If the dependencies for this option are not satisfied, ignore it and remove any previous (e.g.
            # 'required') errors generated for it.
            if not self.depends_satisfied(d, field.depends):
                self.errors.pop(field.name, None)
                continue

            if field.field_type.CHOICE:
                # For CHOICE fields, also check depends on the selected option. A missing value here means validation
                # already failed in our super, so we can ignore those fields
                option = d.get(field.name, None)
                if option and not self.depends_satisfied(d, option.depends):
                    self.add_error_by_code(field.name, 'invalid_choice', value=option.title)

    def save(self, registration):
        d = self.cleaned_data

        fields = self.event.registration_fields.filter(Q(invite_only=None) | Q(invite_only__user=self.user))
        fields = fields.exclude(field_type=RegistrationField.types.SECTION)

        for field in fields:
            value = registration.active_options_by_name.get(field.name, None)
            depends_satisfied = self.depends_satisfied(d, field.depends)

            # Skip fields whose value was not changed (relative to the db, not relative to the form defaults)
            if value and depends_satisfied and field.name not in self.changed_data:
                continue

            # Never change unchangeable fields
            if not field.allow_change:
                continue

            # For active registrations, keep history by marking the current value inactive (a new value will be created
            # below, then). For draft, the existing value will just be reused.
            if value and not registration.status.DRAFT:
                value.active = None
                value.save()
                value = None

            # If the dependencies for this option are not satisfied, delete any values for it that might be present
            # (only for draft, no need to keep history there)
            if not depends_satisfied:
                if value and registration.status.DRAFT:
                    value.delete()
                continue

            if value is None:
                value = RegistrationFieldValue(registration=registration, field=field, active=True)

            if field.field_type.CHOICE:
                value.option = d[field.name]
            elif field.field_type.IMAGE:
                if d[field.name]:
                    value.file_value = d[field.name]
                else:
                    value.file_value = ""
            elif field.field_type.CHECKBOX or field.field_type.UNCHECKBOX:
                value.string_value = RegistrationFieldValue.CHECKBOX_VALUES[d[field.name]]
            else:
                value.string_value = d[field.name]
            value.save()
