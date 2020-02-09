from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from konst import Constant, Constants
from konst.models.fields import ConstantChoiceField

from apps.registrations.models import Registration


class ConsentLog(models.Model):
    """ Log entries about consent given or withdrawn. """

    actions = Constants(
        Constant(CONSENTED=0),
        Constant(WITHDRAWN=1),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    registration = models.ForeignKey(Registration, null=True, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True, null=False)
    action = ConstantChoiceField(constants=actions, null=False)
    consent_name = models.CharField(
        verbose_name=_('Consent for'),
        help_text=_('Internal name for this consent'),
        max_length=32,
    )
    consent_description = models.CharField(
        verbose_name=_('Consent description'),
        help_text=_('What has the user agreed to exactly?'),
        max_length=255,
    )

    # TODO: __str__?
    # TODO: Enforce read-only at model level (e.g. only allow creating new instances, not saving existing ones)?
