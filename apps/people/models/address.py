import reversion
from django.conf import settings
from django.db import models
from django.utils.translation import gettext
from django.utils.translation import ugettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


@reversion.register()
class Address(models.Model):
    """Address information linked to a single ArtaUser."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone_number = PhoneNumberField(verbose_name=_('Phone number'))
    address = models.CharField(max_length=100, verbose_name=_('Address'))
    postalcode = models.CharField(max_length=10, verbose_name=_('Postal code'))
    city = models.CharField(max_length=100, verbose_name=_('City of residence'))
    country = models.CharField(max_length=100, verbose_name=_('Country'))

    def __str__(self):
        return gettext('Address of user %(user)s') % {'user': self.user}

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
