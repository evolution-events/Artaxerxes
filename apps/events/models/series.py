import reversion
from django.db import models
from django.utils.translation import ugettext_lazy as _

from arta.common.db import UpdatedAtQuerySetMixin


class SeriesQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    pass


class SeriesManager(models.Manager.from_queryset(SeriesQuerySet)):
    def get_by_natural_key(self, name):
        return self.get(name=name)


@reversion.register()
class Series(models.Model):
    """Information about a Series of Events."""

    name = models.CharField(max_length=100, verbose_name=_('Name'))
    url = models.CharField(max_length=100, verbose_name=_('Url'))
    email = models.CharField(max_length=100, verbose_name=_('E-mail address of game masters / organisation'))

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = SeriesManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    class Meta:
        verbose_name = _('series')
        verbose_name_plural = _('series')
