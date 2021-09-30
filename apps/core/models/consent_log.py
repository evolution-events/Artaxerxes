from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from konst import Constant, Constants
from konst.models.fields import ConstantChoiceField

from apps.registrations.models import Registration


class ConsentLogQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
        raise NotImplementedError("Deleting consent impossible")


class ConsentLogManager(models.Manager.from_queryset(ConsentLogQuerySet)):
    def create(self, *args, **kwargs):
        raise NotImplementedError("Use ConsentLog.log_consent instead")


class ConsentLog(models.Model):
    """ Log entries about consent given or withdrawn. """

    actions = Constants(
        Constant(CONSENTED=0),
        Constant(WITHDRAWN=1),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    registration = models.ForeignKey(Registration, null=True, on_delete=models.SET_NULL)
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

    objects = ConsentLogManager()

    @classmethod
    def log_consent(cls, *, consent_name, value, user, form_field, registration=None):
        """ Helper to create a ConsentLog instance. """
        ConsentLog(
            user=user,
            registration=registration,
            action=cls.actions.CONSENTED if value else cls.actions.WITHDRAWN,
            consent_name=consent_name,
            consent_description="{} | {}".format(form_field.label, form_field.help_text),
        ).save()

    def save(self, *args, **kwargs):
        if self.id is None:
            super(ConsentLog, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Deleting consent impossible")

    def __str__(self):
        res = "{} {} consent for {}{} at {}".format(
            self.user,
            "provided" if self.action.CONSENTED else "withdrawn",
            self.consent_name,
            (" for {}".format(self.registration.event)) if self.registration else "",
            self.timestamp,
        )

        return res
