import reversion
from django.db import models
from django.utils.translation import ugettext_lazy as _


class RegistrationFieldManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


@reversion.register(follow=('event', 'options'))
class RegistrationField(models.Model):
    """ A field that should get a value during registration for a specific event.  """

    TYPE_CHOICE = 'choice'
    TYPE_STRING = 'string'
    TYPE_CHOICES = (
        (TYPE_CHOICE, _('Choice')),
        (TYPE_STRING, _('String')),
    )

    event = models.ForeignKey('events.Event', related_name='registration_fields', on_delete=models.CASCADE)
    order = models.IntegerField(default=1)
    title = models.CharField(max_length=100)
    name = models.CharField(max_length=20)
    field_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    depends = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                                on_delete=models.SET_NULL)
    invite_only = models.ForeignKey('auth.Group', null=True, blank=True, on_delete=models.SET_NULL)
    allow_change_until = models.DateField(null=True, blank=True)

    objects = RegistrationFieldManager()

    def __str__(self):
        return _('Field %(name)s for %(event)s') % {
            'name': self.name, 'event': self.event,
        }

    def natural_key(self):
        return (self.name,)

    class Meta:
        verbose_name = _('registration field')
        verbose_name_plural = _('registration fields')

        constraints = [
            models.UniqueConstraint(fields=['event', 'name'], name='unique_name_for_event'),
        ]
