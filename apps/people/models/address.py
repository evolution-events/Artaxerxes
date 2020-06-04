import reversion
from django.conf import settings
from django.db import models
from django.utils.translation import gettext
from django.utils.translation import ugettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.utils import UpdatedAtQuerySetMixin


class AddressQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    pass


class AddressManager(models.Manager.from_queryset(AddressQuerySet)):
    pass


@reversion.register(fields=('user',), follow=('user',))
class Address(models.Model):
    """Address information linked to a single ArtaUser."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone_number = PhoneNumberField(verbose_name=_('Phone number'))
    address = models.CharField(max_length=100, verbose_name=_('Address'), blank=True, help_text=_('Optional'))
    postalcode = models.CharField(max_length=10, verbose_name=_('Postal code'), blank=True, help_text=_('Optional'))
    city = models.CharField(max_length=100, verbose_name=_('City of residence'), blank=True, help_text=_('Optional'))
    country = models.CharField(max_length=100, verbose_name=_('Country'), blank=True, help_text=_('Optional'))

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = AddressManager()

    def __str__(self):
        return gettext('Address of user %(user)s') % {'user': self.user}

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
