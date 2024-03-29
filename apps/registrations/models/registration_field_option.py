import reversion
from django.db import models
from django.db.models import Count, Q
from django.utils.translation import ugettext_lazy as _

from apps.core.fields import MonetaryField
from arta.common.db import UpdatedAtQuerySetMixin

from . import Registration, RegistrationField


class RegistrationFieldOptionQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    def with_used_slots(self):
        return self.annotate(
            used_slots=Count(
                'registrationfieldvalue',
                filter=Q(
                    registrationfieldvalue__registration__status=Registration.statuses.REGISTERED,
                    registrationfieldvalue__active=True,
                ),
            ),
        )


class RegistrationFieldOptionManager(models.Manager.from_queryset(RegistrationFieldOptionQuerySet)):
    def get_by_natural_key(self, field, option):
        field = RegistrationField.objects.get_by_natural_key(*field)
        return self.get(field=field, title__iexact=option)


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
    price = MonetaryField(null=True, blank=True)
    admit_immediately = models.BooleanField(
        verbose_name=_('Admit registrations immediately'), default=False,
        help_text=_('When checked, registrations that select this option are admitted immediately, bypassing any '
                    'lottery or similar configured for the event. Has no effect effect when "admit immediately" is '
                    'already set for the event.'))

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = RegistrationFieldOptionManager()

    def __str__(self):
        return self.title

    def natural_key(self):
        return (self.field.natural_key(), self.title)

    class Meta:
        verbose_name = _('registration field option')
        verbose_name_plural = _('registration field options')
        ordering = ('order', 'id')
