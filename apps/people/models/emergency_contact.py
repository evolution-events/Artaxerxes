from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, gettext


class EmergencyContact(models.Model):
    """
    Contact information of the person whom should be notified when an
    emergency occurred which involved the user that this EmergencyContact is connected to.
    """

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
