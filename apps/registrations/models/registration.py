import reversion
from django.conf import settings
from django.db import models
from django.db.models import ExpressionWrapper, Prefetch, Q, Sum, Value
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from konst import Constant, ConstantGroup, Constants
from konst.models.fields import ConstantChoiceField

from apps.core.fields import MonetaryField
from arta.common.db import QExpr, UpdatedAtQuerySetMixin


class RegistrationQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    def with_price(self):
        return self.annotate(
            price=ExpressionWrapper(
                Sum('options__option__price'),
                output_field=MonetaryField()),
        )

    def with_has_conflicting_registrations(self):
        """ Annotates with whether any conflicting registrations exists. """
        return self.annotate(
            # Disabled until this can be made more configurable (and replaced with literal False to work around
            # https://code.djangoproject.com/ticket/33073).
            # has_conflicting_registrations=Exists(Registration.objects.conflicting_registrations_for(FromOuterRef())),
            has_conflicting_registrations=ExpressionWrapper(Value(False), output_field=models.BooleanField()),
        )

    def conflicting_registrations_for(self, registration):
        """ Returns queryset of other registrations that would prevent finalizing the passed registration. """
        # Disabled until this can be made more configurable
        return self.none()

    def prefetch_options(self):
        from . import RegistrationFieldValue

        return self.prefetch_related(Prefetch(
            'options',
            queryset=RegistrationFieldValue.objects.select_related('field', 'option'),
        ))

    def current_for(self, event, user):
        """
        Returns the current registration for the given event and user.

        This returns a queryset that contains at most 1 result, not a model instance or none, call .first() on it if
        you need that (not done here since that forces evaluation of the queryset).
        """
        return (
            self.filter(event=event, user=user)
            .order_by('-is_current', '-created_at')
        )[:1]


class RegistrationManager(models.Manager.from_queryset(RegistrationQuerySet)):
    def get_queryset(self):
        """
        Returns a querysets annotated with:

         - is_current, indicating that this is the current (i.e. non-cancelled) registration for this user and event.
        """
        return super().get_queryset().annotate(
            is_current=QExpr(~Q(status=Registration.statuses.CANCELLED)),
        )


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
        Constant(PENDING=5, label=_('Pending')),
        ConstantGroup("ACTIVE", ("REGISTERED", "WAITINGLIST", "PENDING")),
        ConstantGroup("DRAFT", ("PREPARATION_IN_PROGRESS", "PREPARATION_COMPLETE")),
        ConstantGroup("FINALIZED", ("REGISTERED", "WAITINGLIST", "CANCELLED", "PENDING")),
        ConstantGroup("CURRENT", ("PREPARATION_IN_PROGRESS", "PREPARATION_COMPLETE",
                                  "REGISTERED", "WAITINGLIST", "PENDING")),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE,
                             related_name='registrations')
    event = models.ForeignKey('events.Event', null=False, on_delete=models.CASCADE,
                              related_name='registrations')
    status = ConstantChoiceField(verbose_name=_('Status'), constants=statuses, null=False)
    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True, null=False)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True, null=False)
    registered_at = models.DateTimeField(verbose_name=_('Registration timestamp'), blank=True, null=True)

    objects = RegistrationManager()

    @cached_property
    def waitinglist_above(self):
        return Registration.objects.filter(
            event=self.event_id,
            status=Registration.statuses.WAITINGLIST,
            registered_at__lt=self.registered_at,
        ).count()

    @cached_property
    def admit_immediately(self):
        return self.event.admit_immediately or self.options.filter(option__admit_immediately=True).exists()

    @cached_property
    def options_by_name(self):
        """
        Returns RegistrationFieldValue objects for this Registration by name.

        Returns a dict from RegistrationField.name to RegistrationFieldValue for all fields with values. Works most
        efficient when prefetch_options() was called on the queryset.
        """
        return {value.field.name: value for value in self.options.all()}

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
            # Index to speed up Event.used_slots_for lookups
            models.Index(fields=['event', 'status'],
                         name='idx_event_status'),
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
