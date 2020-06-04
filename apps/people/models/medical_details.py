import reversion
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext
from django.utils.translation import ugettext_lazy as _

from apps.core.utils import UpdatedAtQuerySetMixin


class MedicalDetailsQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    pass


class MedicalDetailsManager(models.Manager.from_queryset(MedicalDetailsQuerySet)):
    pass


@reversion.register(fields=('user',), follow=('user',))
class MedicalDetails(models.Model):
    """ Medical information linked to a single ArtaUser """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='medical_details')
    food_allergies = models.TextField(
        verbose_name=_('Food allergies'),
        help_text=_("Please specify any allergies that our kitchen staff should take into account. Please also "
                    "mention the severity. Do not use this field for food you dislike, only enter things "
                    "that can cause real problems. Leave blank when you have no allergies. "),
        blank=True,
    )

    event_risks = models.TextField(
        verbose_name=_('Take into account for event'),
        help_text=_("Please specify any medical or psychological conditions that we should take into account while "
                    "preparing for the event. For example if you are allergic to smoke machines, can not handle "
                    "flashes of light, are claustrophobic etc. Leave blank when there is nothing to mention."),
        blank=True,
    )

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = MedicalDetailsManager()

    def __str__(self):
        return gettext('Medical details of user %(user)s') % {'user': self.user}

    class Meta:
        verbose_name = _('medical details')
        verbose_name_plural = _('medical details')

        constraints = [
            models.CheckConstraint(check=~Q(food_allergies='', event_risks=''),
                                   name='medical_details_not_empty'),
        ]
