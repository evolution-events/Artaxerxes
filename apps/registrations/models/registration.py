import reversion
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _


@reversion.register(follow=('options',))
class Registration(models.Model):
    """
    Information about a Registration.

    A Registration is the link between a User and an Event.
    """

    STATUS_PREPARATION_IN_PROGRESS = 0
    STATUS_PREPARATION_COMPLETE = 1
    STATUS_REGISTERED = 2
    STATUS_WAITINGLIST = 3
    STATUS_CANCELLED = 4

    STATUS_CHOICES = (
        (STATUS_PREPARATION_IN_PROGRESS, _('Preparation in progress')),
        (STATUS_PREPARATION_COMPLETE, _('Preparation complete')),
        (STATUS_REGISTERED, _('Registered')),
        (STATUS_WAITINGLIST, _('Waiting list')),
        (STATUS_CANCELLED, _('Cancelled')),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    event = models.ForeignKey('events.Event', null=False, on_delete=models.CASCADE)
    status = models.IntegerField(verbose_name=_('Status'), choices=STATUS_CHOICES, null=False)
    registered_at = models.DateTimeField(verbose_name=_('Registration timestamp'), auto_now_add=True, null=False)

    def __str__(self):
        return _('%(user)s - %(event)s - %(status)s') % {
            'user': self.user, 'event': self.event, 'status': self.get_status_display(),
        }

    class Meta:
        verbose_name = _('registration')
        verbose_name_plural = _('registrations')

    # Put this outside of the meta class, so we can access the STATUS_ constants
    # https://stackoverflow.com/a/8366758/740048
    Meta.constraints = [
        models.UniqueConstraint(fields=['event', 'user'], condition=~Q(status=STATUS_CANCELLED),
                                name='one_registration_per_user_per_event'),
    ]
