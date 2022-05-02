import reversion
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from konst import Constant, Constants
from konst.models.fields import ConstantChoiceField

from apps.core.fields import MonetaryField


class PaymentQuerySet(models.QuerySet):
    pass


class PaymentManager(models.Manager.from_queryset(PaymentQuerySet)):
    pass


@reversion.register(follow=('registration',))
class Payment(models.Model):
    """ A payment for a registration. """

    statuses = Constants(
        Constant(PENDING=0, label=_('Payment in progress')),
        Constant(COMPLETED=1, label=_('Payment completed')),
        Constant(FAILED=2, label=_('Payment failed/expired/aborted/etc.')),
    )

    registration = models.ForeignKey('registrations.Registration', related_name='payments', on_delete=models.CASCADE)

    amount = MonetaryField()
    status = ConstantChoiceField(verbose_name=_('Status'), constants=statuses, null=False, default=statuses.PENDING)

    # null=True to allow non-unique blank values
    mollie_id = models.CharField(max_length=16, unique=True, blank=True, null=True, default=None)
    mollie_status = models.CharField(max_length=16, blank=True)

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True, null=False)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True, null=False)
    timestamp = models.DateTimeField(verbose_name=_('Transaction date/time'), null=True)

    objects = PaymentManager()

    @cached_property
    def type(self):
        if self.mollie_id:
            return _("Online payment")
        else:
            return _("Manual payment")

    def __str__(self):
        return "{} for {} for {} ({} / {})".format(
            self.amount,
            self.registration.event,
            self.registration.user,
            self.status.id,
            self.mollie_status,
        )

    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')

        # Ensure that custom manager / queryset methods are also available on related managers
        base_manager_name = 'objects'

        constraints = [
            models.CheckConstraint(
                # mollie_id can be null (which avoids uniqueness constraints), but cannot be the empty string
                check=~Q(mollie_id=""),
                name='mollie_id_cannot_be_empty',
            ),
            models.CheckConstraint(
                check=(Q(mollie_id=None) & Q(mollie_status="")) | (~Q(mollie_id=None) & ~Q(mollie_status="")),
                name='mollie_id_and_status_set_or_unset_together',
            ),
        ]
