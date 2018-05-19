from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class Registration(models.Model):
    """
    Information about a Registration. A Registration is the link between a User
    and an Event.
    """
    STATUS_REGISTERED = 0
    STATUS_WAITINGLIST = 1
    STATUS_CANCELLED = 2

    STATUS_CHOICES = (
        (STATUS_REGISTERED, _('Registered')),
        (STATUS_WAITINGLIST, _('Waiting list')),
        (STATUS_CANCELLED, _('Cancelled')),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    event = models.ForeignKey('events.Event', null=False, on_delete=models.CASCADE)
    status = models.IntegerField(verbose_name=_('Status'), choices=STATUS_CHOICES, null=False)

    def __str__(self):
        return _('%(user)s - %(event)s - %(status)s') % {'user': self.user, 'event': self.event, 'status': self.get_status_display()}

    class Meta:
        verbose_name = _('registration')
        verbose_name_plural = _('registrations')
