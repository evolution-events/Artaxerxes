import reversion
from django.db import models
from django.db.models import Count, Q
from django.utils.translation import ugettext_lazy as _

from . import Registration, RegistrationField


class RegistrationFieldOptionManager(models.Manager):
    def get_by_natural_key(self, field, option):
        field = RegistrationField.objects.get_by_natural_key(*field)
        return self.get(field=field, title__iexact=option)

    def with_used_slots(self):
        return self.get_queryset().annotate(
            used_slots=Count(
                'registrationfieldvalue',
                filter=Q(registrationfieldvalue__registration__status=Registration.statuses.REGISTERED),
            ),
        )


@reversion.register(follow=('field',))
class RegistrationFieldOption(models.Model):
    """ One of multiple options that can be assigned to a given field. """

    field = models.ForeignKey('registrations.RegistrationField', related_name='options', on_delete=models.CASCADE)
    order = models.IntegerField(default=1)
    title = models.CharField(max_length=100)
    depends = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                                on_delete=models.SET_NULL)
    invite_only = models.ForeignKey('auth.Group', null=True, blank=True, on_delete=models.SET_NULL)
    slots = models.IntegerField(null=True, blank=True)
    full = models.BooleanField(default=False)
    price = models.FloatField(null=True, blank=True)

    objects = RegistrationFieldOptionManager()

    def __str__(self):
        return self.title

    def natural_key(self):
        return (self.field.natural_key(), self.title)

    class Meta:
        verbose_name = _('registration field option')
        verbose_name_plural = _('registration field options')
        ordering = ('order', 'title')
