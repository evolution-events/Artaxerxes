import reversion
from django.db import models
from django.utils.translation import ugettext_lazy as _


@reversion.register()
class RegistrationFieldValue(models.Model):
    """ The actual value for a given field on a given registration. """

    registration = models.ForeignKey('registrations.Registration', on_delete=models.CASCADE)
    field = models.ForeignKey('registrations.RegistrationField', on_delete=models.CASCADE)
    option = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                               on_delete=models.CASCADE)
    string_value = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        if self.option:
            value = self.option.title
        else:
            value = self.string_value

        return _('Value for %(field)s for %(registration)s: %(value)s') % {
            'field': self.field.name, 'registration': self.registration, 'value': value,
        }

    class Meta:
        verbose_name = _('registration field value')
        verbose_name_plural = _('registration field values')

        constraints = [
            models.UniqueConstraint(fields=['registration', 'field'], name='one_value_per_field_per_registration'),
        ]
