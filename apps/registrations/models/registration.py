import reversion
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from konst import Constant, ConstantGroup, Constants
from konst.models.fields import ConstantChoiceField


@reversion.register(follow=('options',))
class Registration(models.Model):
    """
    Information about a Registration.

    A Registration is the link between a User and an Event.
    """

    statuses = Constants(
        Constant(PREPARATION_IN_PROGRESS=0, label=_('Preparation in progress')),
        Constant(PREPARATION_COMPLETE=1, label=_('Preparation complete')),
        Constant(REGISTERED=2, label=_('Registered')),
        Constant(WAITINGLIST=3, label=_('Waiting list')),
        Constant(CANCELLED=4, label=_('Cancelled')),
        ConstantGroup("ACTIVE", ("REGISTERED", "WAITINGLIST")),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    event = models.ForeignKey('events.Event', null=False, on_delete=models.CASCADE)
    status = ConstantChoiceField(verbose_name=_('Status'), constants=statuses, null=False)
    registered_at = models.DateTimeField(verbose_name=_('Registration timestamp'), auto_now_add=True, null=False)

    def __str__(self):
        return _('%(user)s - %(event)s - %(status)s') % {
            'user': self.user, 'event': self.event, 'status': self.get_status_display(),
        }

    class Meta:
        verbose_name = _('registration')
        verbose_name_plural = _('registrations')

    # Put this outside of the meta class, so we can access the statuses constants
    # https://stackoverflow.com/a/8366758/740048
    Meta.constraints = [
        models.UniqueConstraint(fields=['event', 'user'], condition=~Q(status=statuses.CANCELLED),
                                name='one_registration_per_user_per_event'),
    ]
