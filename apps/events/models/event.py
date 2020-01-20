import reversion
from django.conf import settings
from django.db import models
from django.db.models import Count, Max, Q
from django.db.models.functions import Now
from django.utils.translation import ugettext_lazy as _

from apps.core.utils import QExpr
from apps.registrations.models import Registration

from .series import Series


class EventManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)

    def for_user(self, user, with_registration_status=False):
        """
        Returns events annotated with properties applicable for the given user.

         - is_visible: True when the user can view this event
         - preregistration_is_open: True when the user can prepare a registration (becomes False again when
           registration_is_open becomes True).
         - registration_is_open: True when the user can finalize a registration.
         - registration_status: The status of the registration for the user for this event, or None when no
           registration is present. Cancelled registrations are ignored by this status.
        """
        # This does not use the user yet, but this makes it easier to change that later
        # This essentially duplicates the similarly-named methods on the model below.
        # Split into multiple annotates to allow using annotations in subsequent annotations (the order of these can
        # not be guaranteed in the kwargs across systems)
        qs = self.get_queryset().annotate(
            is_visible=QExpr(public=True),
        ).annotate(
            registration_is_open=QExpr(
                Q(is_visible=True)
                & ~Q(registration_opens_at=None)
                & Q(registration_opens_at__lt=Now())
                & Q(start_date__gt=Now()),
            ),
        ).annotate(
            preregistration_is_open=QExpr(
                Q(is_visible=True)
                & Q(registration_is_open=False)
                & Q(start_date__gt=Now()),
            ),
        )
        if with_registration_status:
            # This looks for all non-cancelled registrations related to this event and user. Due to a constraint, this
            # should be either one or none, never multiple. This uses the Max function to get at the status of that one
            # registration, but e.g. Sum would also have worked. When no registrations are present, this returns None
            # (since MAX(NULL) is still NULL).
            qs = qs.annotate(registration_status=Max(
                'registration__status',
                filter=Q(registration__user=user) & ~Q(registration__status=Registration.statuses.CANCELLED),
            ))
        return qs

    def with_used_slots(self):
        return self.get_queryset().annotate(
            used_slots=Count(
                'registration',
                filter=Q(registration__status=Registration.statuses.REGISTERED),
            ),
        )


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

    slots = models.IntegerField(
        null=True, blank=True,
        help_text=_('Maximum number of attendees for this event. If omitted, no there is no limit.'))
    full = models.BooleanField(default=False)

    user = models.ManyToManyField(settings.AUTH_USER_MODEL, through=Registration)

    objects = EventManager()

    def display_name(self):
        if not self.title:
            return self.name
        else:
            return "{0}: {1}".format(self.name, self.title)

    def __str__(self):
        return self.display_name()

    def natural_key(self):
        return (self.name,)

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')
