import reversion
from django.db import models
from django.utils.translation import ugettext_lazy as _


@reversion.register(follow=('registration',))
class RegistrationFieldValue(models.Model):
    """ The actual value for a given field on a given registration. """

    registration = models.ForeignKey('registrations.Registration', related_name='options', on_delete=models.CASCADE)
    field = models.ForeignKey('registrations.RegistrationField', on_delete=models.CASCADE)
    option = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                               on_delete=models.CASCADE)
    string_value = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.display_value()

    def display_value(self):
        if self.field.field_type == self.field.TYPE_CHOICE:
            if self.option:
                return self.option.title
            else:
                return "<value unset>"
        return self.string_value

    @property
    def price(self):
        if self.field.field_type == self.field.TYPE_CHOICE and self.option:
            return self.option.price
        return None

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
