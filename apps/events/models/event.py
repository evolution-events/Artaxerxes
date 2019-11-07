import reversion
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from .registration import Registration
from .series import Series


@reversion.register()
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
        verbose_name=_('Description'), help_text=_('Event details like what is included or not'))
    start_date = models.DateField(verbose_name=_('Start date'))
    end_date = models.DateField(verbose_name=_('End date'))
    url = models.CharField(
        max_length=100, verbose_name=_('Url'), blank=True,
        help_text=_('Can be left blank if event is part of a series, then value of series will be used.'))
    email = models.CharField(
        max_length=100, verbose_name=_('E-mail address of game masters / organisation'), blank=True,
        help_text=_('Can be left blank if event is part of a series, then value of series will be used.'))
    location_name = models.CharField(
        max_length=100, verbose_name=_('Location name'),
        help_text=_('Name of the location, will be used as link text if url is also available'))
    location_url = models.CharField(
        max_length=100, verbose_name=_('Location url'), blank=True, help_text=_('Url of location website'))
    location_info = models.TextField(
        verbose_name=('Location information'), help_text=_('Address and additional information about the location'))
    user = models.ManyToManyField(settings.AUTH_USER_MODEL, through=Registration)

    def display_name(self):
        if not self.title:
            return self.name
        else:
            return "{0}: {1}".format(self.name, self.title)

    def __str__(self):
        return self.display_name()

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')
