import reversion
from django.db import models
from django.db.models import Case, Q, When
from django.utils.translation import ugettext_lazy as _

from arta.common.db import QExpr, UpdatedAtQuerySetMixin

from . import RegistrationField


class RegistrationFieldValueQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    def with_satisfies_required(self):
        """
        Add satisfies_required annotation.

        This indicates whether this value is sufficient to satisfy the requirements of its field (based on type and its
        required attribute).
        """
        CHECKED = RegistrationFieldValue.CHECKBOX_VALUES[True]
        UNCHECKED = RegistrationFieldValue.CHECKBOX_VALUES[False]

        types = RegistrationField.types
        return self.annotate(satisfies_required=QExpr(
            Q(field__field_type=types.CHOICE) & (Q(field__required=False) | ~Q(option=None))
            | Q(field__field_type=types.IMAGE) & (Q(field__required=False) | ~Q(file_value=""))
            | Q(field__field_type=types.STRING) & (Q(field__required=False) | ~Q(string_value=""))
            | Q(field__field_type=types.TEXT) & (Q(field__required=False) | ~Q(string_value=""))
            | Q(field__field_type=types.RATING5) & (Q(field__required=False) | ~Q(string_value=""))
            # Checkbox is slightly different, it must be checked when required, or any (non-empty) value otherwise
            | (Q(field__field_type=types.CHECKBOX) | Q(field__field_type=types.UNCHECKBOX)) & (
                Q(field__required=False) & Q(string_value=UNCHECKED) | Q(string_value=CHECKED)
            ),
        ))

    def select_related_option_and_field(self):
        """ Wrapper for select_related, to be used from templates """
        return self.select_related('option', 'field')

    def only_active(self):
        """ Select active values only """
        # This is a simple filter, but exists in case we need to change the way this is stored later
        return self.filter(active=True)

    def priced_only(self):
        return self.exclude(option=None).exclude(option__price=None)


class RegistrationFieldValueManager(models.Manager.from_queryset(RegistrationFieldValueQuerySet)):
    pass


def file_value_path(obj, filename):
    """ Generate the filename of an uploaded file """
    return 'registration_fields/event_{0}/field_{1}/{2}-{3}'.format(
        obj.registration.event_id, obj.field_id, obj.id, filename)


@reversion.register(follow=('registration',))
class RegistrationFieldValue(models.Model):
    """ The actual value for a given field on a given registration. """

    registration = models.ForeignKey('registrations.Registration', related_name='options', on_delete=models.CASCADE)
    field = models.ForeignKey('registrations.RegistrationField', on_delete=models.CASCADE)
    option = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                               on_delete=models.CASCADE)
    string_value = models.TextField(blank=True)
    # TODO: Delete unused files, see https://stackoverflow.com/questions/16041232/django-delete-filefield
    # TODO: When used with arbitrary files, instead of images (verified by forms.ImageField), additionaly measures are
    # needed to prevent security issues.
    file_value = models.FileField(blank=True, upload_to=file_value_path)

    active = models.BooleanField(
        null=True, default=True,
        help_text=_('Set to null when this value is replaced by a new value'),
    )

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = RegistrationFieldValueManager()

    # string_values used to encode checkbox values
    CHECKBOX_VALUES = {
        False: '0',
        True: '1',
    }

    def __str__(self):
        return self.display_value()

    def display_value(self):
        if self.field.field_type.CHOICE:
            if self.option:
                return self.option.title
        elif self.field.field_type.CHECKBOX or self.field.field_type.UNCHECKBOX:
            if self.string_value is not None:
                if self.string_value == self.CHECKBOX_VALUES[True]:
                    return str(_('Yes'))
                elif self.string_value == self.CHECKBOX_VALUES[False]:
                    return str(_('No'))
                else:
                    return "<invalid>"
        elif self.field.field_type.IMAGE:
            return self.file_value.name
        else:
            if self.string_value is not None:
                return self.string_value
        return "<value unset>"
    display_value.admin_order_field = Case(
        When(field__field_type=RegistrationField.types.CHOICE, then='option__title'),
        default_value='string_value',
    )

    def price(self):
        if self.field.field_type.CHOICE and self.option:
            return self.option.price
        return None
    price.admin_order_field = 'option__price'
    price = property(price)

    @classmethod
    def group_by_section(self, values):
        """
        Group an iterable (or queryset) of active RegistrationFieldValue by the section of related field.

        This returns a list of (section, values) tuples, where section is a RegistrationField option, and values is a
        list of RegistrationFieldValue objects. The resulting values are ordered based on the field ordering, but only
        values in the iterable passed are returned (and empty sections are omitted).

        Each field should occur at most once in the passed iterable (i.e. passing active values for one registration).
        """
        our_options = {value.field_id: value for value in values}
        if not our_options:
            return
        any_option = next(iter(our_options.values()))
        event_id = any_option.field.event_id

        all_fields = RegistrationField.objects.all().filter(event=event_id)
        section = None
        fields = []

        for field in all_fields:
            if field.field_type.SECTION:
                if fields:
                    yield (section, fields)
                section = field
                fields = []
            elif field.id in our_options:
                fields.append(our_options[field.pk])

        if fields:
            yield (section, fields)

    class Meta:
        verbose_name = _('registration field value')
        verbose_name_plural = _('registration field values')
        # Ensure that custom manager / queryset methods are also available on related managers
        base_manager_name = 'objects'

        constraints = [
            # We would like to use a condition of active=True on this constraint (so only the active registrations have
            # to be unique), but Mysql/Mariadb does not support this. So instead we use active=None for old entried,
            # which count as unique entries. This is enforced by forbidding active=False.
            models.UniqueConstraint(
                fields=['registration', 'field', 'active'],
                name='one_active_value_per_field_per_registration',
            ),
            models.CheckConstraint(check=~Q(active=False), name='active_cannot_be_false'),
        ]
        indexes = [
            # Index to speed up lookups from option through here to registration (e.g. get all registrations that use a
            # given option) and vice versa (e.g. get all options used by a registration), which can now be done using
            # just these indices.
            models.Index(fields=['option', 'registration'], name='idx_option_registration'),
            models.Index(fields=['registration', 'option'], name='idx_registration_option'),
            # And another pair to filter only active ones
            models.Index(fields=['active', 'option', 'registration'], name='idx_active_option_registration'),
            models.Index(fields=['active', 'registration', 'option'], name='idx_active_registration_option'),
        ]
