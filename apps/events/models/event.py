import reversion
from django.conf import settings
from django.db import models
from django.db.models import Case, Count, F, Q, When
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from apps.registrations.models import Registration
from arta.common.db import QExpr, UpdatedAtQuerySetMixin

from .series import Series


class EventQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    def for_user(self, user, with_registration=False):
        """
        Returns events annotated with properties applicable for the given user.

         - is_visible: True when the user can view this event
         - preregistration_is_open: True when the user can prepare a registration (becomes False again when
           registration_is_open becomes True).
         - registration_is_open: True when the user can finalize a registration.

         When with_registration is given, also:
         - registration: The current registration for the user for this event, or None when no
           registration is current. Current is the one non-cancelled registration, or most recent cancelled
           registration.
        """
        now = timezone.now()
        # This does not use the user yet, but this makes it easier to change that later
        # This essentially duplicates the similarly-named methods on the model below.
        # Split into multiple annotates to allow using annotations in subsequent annotations (the order of these can
        # not be guaranteed in the kwargs across systems)
        qs = self.annotate(
            is_visible=F('public'),
        ).annotate(
            registration_is_open=QExpr(
                Q(is_visible=True)
                & ~Q(registration_opens_at=None)
                & Q(registration_opens_at__lte=now)
                & Q(start_date__gt=now),
            ),
        ).annotate(
            preregistration_is_open=QExpr(
                Q(is_visible=True)
                & Q(registration_is_open=False)
                & Q(start_date__gt=now),
            ),
        )
        if with_registration:
            # This looks for all related registrations, and picks the current one (should be at most one), or if there
            # is not, the most recent cancelled one.
            qs = qs.annotate(registration_id=models.Subquery(
                Registration.objects.current_for(
                    event=models.OuterRef('pk'),
                    user=user,
                ).values('pk'),
            ))
            # Also annotate the status, to allow filtering on that.
            # TODO: It would be better if the registration instance was annotated directly (and would also support
            # select_related, prefetch_related or filtering), but it seems Django does not currently support this
            # currently. See https://code.djangoproject.com/ticket/27414#comment:3
            qs = qs.annotate(registration_status=models.Subquery(
                Registration.objects.current_for(
                    event=models.OuterRef('pk'),
                    user=user,
                ).values('status'),
            ))
        return qs

    def with_used_slots(self):
        """
        Adds used_slots annotation.

        This is the number of slots used (i.e. the number of REGISTERED registrations) for the given event.
        """
        return self.annotate(
            used_slots=Count(
                'registrations',
                filter=Q(registrations__status=Registration.statuses.REGISTERED),
            ),
        )

    def used_slots_for(self, event):
        """ Returns the number of slots used (i.e. the number of REGISTERED registrations) for the given event. """
        return Registration.objects.filter(event=event, status=Registration.statuses.REGISTERED).count()


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    def get_by_natural_key(self, name):
        return self.get(name=name)


@reversion.register(follow=('registration_fields',))
class Event(models.Model):
    """Information about an Event."""

    series = models.ForeignKey(
        Series, null=True, blank=True, on_delete=models.CASCADE, verbose_name=_('Series this event is part of'))
    name = models.CharField(
        max_length=100, verbose_name=_('Name'),
        help_text=_('Name of the event. Unique if this is a oneshot, name of the series plus a number if part of a '
                    'series. Do not forget the X when this is your only title.'))
    title = models.CharField(
        max_length=100, verbose_name=_('Title'), blank=True,
        help_text=_('Actual subtitle when within series. Do not forget the X if the name does not contain it.'))
    description = models.TextField(
        verbose_name=_('Description'), blank=True,
        help_text=_('Event details like what is included or not'))
    start_date = models.DateField(verbose_name=_('Start date'))
    end_date = models.DateField(verbose_name=_('End date'))
    url = models.CharField(
        max_length=100, verbose_name=_('Url'), blank=True,
        help_text=_('Can be left blank if event is part of a series, then value of series will be used.'))
    email = models.CharField(
        max_length=100, verbose_name=_('E-mail address of game masters / organisation'), blank=True,
        help_text=_('Can be left blank if event is part of a series, then value of series will be used.'))
    location_name = models.CharField(
        max_length=100, verbose_name=_('Location name'), blank=True,
        help_text=_('Name of the location, will be used as link text if url is also available'))
    location_url = models.CharField(
        max_length=100, verbose_name=_('Location url'), blank=True, help_text=_('Url of location website'))
    location_info = models.TextField(
        verbose_name=('Location information'), blank=True,
        help_text=_('Address and additional information about the location'))

    registration_opens_at = models.DateTimeField(
        verbose_name=_('Registration opens at'), null=True, blank=True,
        help_text=_('At this time registration is open for everyone.'))
    public = models.BooleanField(
        verbose_name=_('Public'), default=False,
        help_text=_('When checked, the event is visible to users. If registration is not open yet, they can prepare a '
                    'registration already.'))

    admit_immediately = models.BooleanField(
        verbose_name=_('Admit registrations immediately (i.e. "first come, first served")'), default=True,
        help_text=_('When checked, registrations are admitted immediately when finalized (subject to available '
                    'slots), making the registration first come, first served. When unchecked, registrations are set '
                    'to pending, to be admitted through some other process later (e.g. lottery or selection).'))
    pending_mail_text = models.TextField(
        verbose_name=_('Mail text for pending registrations'), blank=True,
        help_text=_('Text to include in the registration confirmation e-mail for pending (e.g. lottery) '
                    'registrations, explaining how admission works.'))
    extra_conditions = models.TextField(
        verbose_name=_('Extra registration conditions'), blank=True,
        help_text=_('These are shown in the list of conditions when finalizing a registration. Rendered inside the '
                    'existing &lt;ul&gt; tag, so should contain &lt;li&gt; tags, but no &lt;ul&gt;.'))

    slots = models.IntegerField(
        null=True, blank=True,
        help_text=_('Maximum number of attendees for this event. If omitted, no there is no limit.'))
    full = models.BooleanField(default=False)

    user = models.ManyToManyField(settings.AUTH_USER_MODEL, through=Registration)

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = EventManager()

    @cached_property
    def registration(self):
        # The registration_id should be set by an annotation in the manager above
        # TODO: It would be better if the registration instance was annotated directly (and would also support
        # select_related or prefetch_related), but it seems Django does not
        # currently support this currently. See https://code.djangoproject.com/ticket/27414#comment:3
        if self.registration_id is None:
            return None
        return Registration.objects.with_price().get(pk=self.registration_id)

    def display_name(self):
        if not self.title:
            return self.name
        else:
            return "{0}: {1}".format(self.name, self.title)
    display_name.admin_order_field = Concat('name', 'title')

    def display_url(self):
        """ Return either own url or the one of the series event is part of, or empty string. """
        if self.url:
            return self.url
        elif self.series and self.series.url:
            return self.series.url
        return ''
    display_url.admin_order_field = Case(
        When(~Q(url=""), then='url'),
        When(~Q(series__url=""), then='series__url'),
        default_value='')

    def display_email(self):
        """ Return either own e-mail or the one of the series event is part of, or empty string. """
        if self.email:
            return self.email
        elif self.series and self.series.email:
            return self.series.email
        return ''
    display_email.admin_order_field = Case(
        When(~Q(email=""), then='email'),
        When(~Q(series__email=""), then='series__email'),
        default_value='')

    def __str__(self):
        return self.display_name()

    def natural_key(self):
        return (self.name,)

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')
        ordering = ('-start_date',)

        indexes = [
            # Index to speed up listing of all public, future events
            models.Index(fields=['public', 'start_date'], name='idx_public_start_date'),
        ]
