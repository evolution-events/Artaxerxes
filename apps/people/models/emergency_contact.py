import reversion
from django.db import models
from django.conf import settings
from django.utils.translation import gettext
from django.utils.translation import ugettext_lazy as _


@reversion.register()
class EmergencyContact(models.Model):
    """Contact information a person to be notified in an emergency involving the associated user."""

    MAX_PER_USER = 3

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contact_name = models.CharField(max_length=100, verbose_name=_('Name of contact'))
    relation = models.CharField(max_length=100, verbose_name=_('Relation to contact'),
                                help_text=_('For example: parent, partner, friend etc.'))
    phone_number = models.CharField(max_length=100, verbose_name=_('Phone number of contact'))
    remarks = models.TextField(verbose_name=_('Remarks'))

    def __str__(self):
        return gettext('Emergency contact of user %(user)s') % {'user': self.user}

    class Meta:
        verbose_name = _('contact')
        verbose_name_plural = _('contacts')