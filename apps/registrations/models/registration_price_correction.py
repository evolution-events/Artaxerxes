import reversion
from django.db import models
from django.db.models import F
from django.utils.translation import ugettext_lazy as _

from apps.core.fields import MonetaryField
from arta.common.db import QExpr, UpdatedAtQuerySetMixin

from . import Registration


class RegistrationPriceCorrectionQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    def with_active(self):
        """ Add active annotation that indicates if this correction is active based on the registration status. """
        return self.annotate(
            is_cancelled=QExpr(registration__status=Registration.statuses.CANCELLED),
            active=QExpr(when_cancelled=F('is_cancelled')),
        )


class RegistrationPriceCorrectionManager(models.Manager.from_queryset(RegistrationPriceCorrectionQuerySet)):
    pass


@reversion.register(follow=('registration',))
class RegistrationPriceCorrection(models.Model):
    """ A one-off correction to the price of a single registration. """

    registration = models.ForeignKey('registrations.Registration', related_name='price_corrections',
                                     on_delete=models.CASCADE)
    description = models.CharField(max_length=100)
    price = MonetaryField(null=True, blank=True)
    when_cancelled = models.BooleanField(
        default=False,
        help_text=_('If and only if this is checked, this correction is applied when the registration is cancelled.'),
    )

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = RegistrationPriceCorrectionManager()

    def __str__(self):
        return "{}: €{}".format(self.description, self.price)

    class Meta:
        verbose_name = _('registration price correction')
        verbose_name_plural = _('registration price corrections')
