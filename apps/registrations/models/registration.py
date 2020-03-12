import reversion
from django.conf import settings
from django.db import models
from django.db.models import ExpressionWrapper, Q, Sum
from django.utils.translation import ugettext_lazy as _
from konst import Constant, ConstantGroup, Constants
from konst.models.fields import ConstantChoiceField

from apps.core.fields import MonetaryField
from apps.core.utils import QExpr


class Manager(models.Manager):
    def get_queryset(self):
        """
        Returns a queryset, annotaded with:

         - is_current, indicating that this is the current (i.e. non-cancelled) registration for this user and event.
        """
        return super().get_queryset().annotate(
            is_current=QExpr(~Q(status=Registration.statuses.CANCELLED)),
        )

    def with_price(self):
        return self.get_queryset().annotate(
            price=ExpressionWrapper(
                Sum('options__option__price'),
                output_field=MonetaryField()),
        )

    def current_for(self, event, user):
        """
        Returns the current registration for the given event and user.

        This returns a queryset that contains at most 1 result, not a model instance or none, call .first() on it if
        you need that (not done here since that forces evaluation of the queryset).
        """
        return (
            self.get_queryset()
            .filter(event=event, user=user)
            .order_by('-is_current', '-created_at')
        )[:1]


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
        ConstantGroup("CURRENT", ("PREPARATION_IN_PROGRESS", "PREPARATION_COMPLETE", "REGISTERED", "WAITINGLIST")),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    event = models.ForeignKey('events.Event', null=False, on_delete=models.CASCADE)
    status = ConstantChoiceField(verbose_name=_('Status'), constants=statuses, null=False)
    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True, null=False)
    registered_at = models.DateTimeField(verbose_name=_('Registration timestamp'), blank=True, null=True)

    objects = Manager()

    def __str__(self):
        return _('%(user)s - %(event)s - %(status)s') % {
            'user': self.user, 'event': self.event, 'status': self.get_status_display(),
        }

    class Meta:
        verbose_name = _('registration')
        verbose_name_plural = _('registrations')

        indexes = [
            # Index to speed up current_for lookups
            models.Index(fields=['user', 'event', 'status', 'created_at'],
                         name='idx_user_event_status_created'),
        ]

    # Put this outside of the meta class, so we can access the statuses constants
    # https://stackoverflow.com/a/8366758/740048
    Meta.constraints = [
        # TODO: UniqueConstraint with condition unsupported on MySQL, but CheckConstraint cannot contain subqueries
        # (or, it seems any reference to other rows either). The only alternative that could work seems to be a trigger
        # that checks the condition. Sqlite does check this, though, so the check is active in development
        # https://mysqlserverteam.com/new-and-old-ways-to-emulate-check-constraints-domain/
        models.UniqueConstraint(fields=['event', 'user'], condition=Q(status__in=statuses.CURRENT),
                                name='one_current_registration_per_user_per_event'),
        models.CheckConstraint(check=~Q(status__in=statuses.ACTIVE) | Q(registered_at__isnull=False),
                               name='active_registration_has_timestamp'),
    ]
