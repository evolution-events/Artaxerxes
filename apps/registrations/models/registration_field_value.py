import reversion
from django.db import models
from django.db.models import Case, Q, When
from django.utils.translation import ugettext_lazy as _

from arta.common.db import UpdatedAtQuerySetMixin

from . import RegistrationField


class RegistrationFieldValueQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    pass


class RegistrationFieldValueManager(models.Manager.from_queryset(RegistrationFieldValueQuerySet)):
    pass


@reversion.register(follow=('registration',))
class RegistrationFieldValue(models.Model):
    """ The actual value for a given field on a given registration. """

    registration = models.ForeignKey('registrations.Registration', related_name='options', on_delete=models.CASCADE)
    field = models.ForeignKey('registrations.RegistrationField', on_delete=models.CASCADE)
    option = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                               on_delete=models.CASCADE)
    string_value = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = RegistrationFieldValueManager()

    def __str__(self):
        return self.display_value()

    def display_value(self):
        if self.field.field_type.CHOICE:
            if self.option:
                return self.option.title
            else:
                return "<value unset>"
        return self.string_value
    display_value.admin_order_field = Case(
        When(field__field_type=RegistrationField.types.CHOICE, then='option__title'),
        default_value = 'string_value',
    )

    def price(self):
        if self.field.field_type.CHOICE and self.option:
            return self.option.price
        return None
    price.admin_order_field = 'option__price'
    price = property(price)

    class Meta:
        verbose_name = _('registration field value')
        verbose_name_plural = _('registration field values')

        constraints = [
            models.UniqueConstraint(fields=['registration', 'field'], name='one_value_per_field_per_registration'),
        ]
        indexes = [
            # Index to speed up lookups from option through here to registration (e.g. get all registrations that use a
            # given option) and vice versa (e.g. get all options used by a registration), which can now be done using
            # just these indices.
            models.Index(fields=['option', 'registration'], name='idx_option_registration'),
            models.Index(fields=['registration', 'option'], name='idx_registration_option'),
        ]
