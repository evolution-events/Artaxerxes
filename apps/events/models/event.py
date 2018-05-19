from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from .series import Series
from .registration import Registration


class Event(models.Model):
    """Information about an Event."""

    series = models.ForeignKey(Series, null=True, blank=True, verbose_name=_('Series this event is part of'), on_delete=models.CASCADE)
    title = models.CharField(max_length=100, verbose_name=_('Title'), help_text=_('Actual subtitle when within series. Do not forget the X when this is your only title.'))
    description = models.TextField(verbose_name=_('Description'), help_text=_('Event details like what is included or not'))
    start_date = models.DateField(verbose_name=_('Start date'))
    end_date = models.DateField(verbose_name=_('End date'))
    url = models.CharField(max_length=100, verbose_name=_('Url'), blank=True, help_text=_('Can be left blank if event is part of a series, then value of series will be used.'))
    email = models.CharField(max_length=100, verbose_name=_('E-mail address of game masters / organisation'), blank=True, help_text=_('Can be left blank if event is part of a series, then value of series will be used.'))
    location_name = models.CharField(max_length=100, verbose_name=_('Location name'), help_text=_('Name of the location, will be used as link text if url is also available'))
    location_url = models.CharField(max_length=100, verbose_name=_('Location url'), blank=True, help_text=_('Url of location website'))
    location_info = models.TextField(verbose_name=('Location information'), help_text=_('Address and additional information about the location'))
    user = models.ManyToManyField(settings.AUTH_USER_MODEL, through=Registration)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')
