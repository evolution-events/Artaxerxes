import reversion
from django.db import models
from django.utils.translation import ugettext_lazy as _


class SeriesManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


@reversion.register()
class Series(models.Model):
    """Information about a Series of Events."""

    name = models.CharField(max_length=100, verbose_name=_('Name'))
    url = models.CharField(max_length=100, verbose_name=_('Url'))
    email = models.CharField(max_length=100, verbose_name=_('E-mail address of game masters / organisation'))

    objects = SeriesManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    class Meta:
        verbose_name = _('series')
        verbose_name_plural = _('series')
