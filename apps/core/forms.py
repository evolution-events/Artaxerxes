import reversion
from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.core.models import ConsentLog
from apps.people.models import ArtaUser

""" Maps ArtaUser boolean attributes to the corresponding consent name """
CONSENT_PREFS = {
    'consent_announcements_nl': 'email_announcements_nl',
    'consent_announcements_en': 'email_announcements_en',
}


class SignupFormBase(forms.Form):
    """ Custom signup form. The allauth default forms (local account and social account) will derive from this.  """

    # TODO: When implementing social accounts, we should probably pre-fill these fields with data from user, as
    # populated by the social provider if available.
    first_name = ArtaUser._meta.get_field('first_name').formfield(required=True)
    last_name = ArtaUser._meta.get_field('last_name').formfield(required=True)
    consent_announcements_nl = ArtaUser._meta.get_field('consent_announcements_nl').formfield()
    consent_announcements_en = ArtaUser._meta.get_field('consent_announcements_en').formfield()

    def signup(self, request, user):
        with reversion.create_revision():
            reversion.set_user(user)
            reversion.set_comment(_("Account created via frontend."))

            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            for attr, _consent_name in CONSENT_PREFS.items():
                setattr(user, attr, self.cleaned_data[attr])
            user.save()

        for (attr, consent_name) in CONSENT_PREFS.items():
            if getattr(user, attr):
                ConsentLog.log_consent(
                    user=user,
                    consent_name=consent_name,
                    value=getattr(user, attr),
                    form_field=self.fields[attr],
                )


class EmailPreferencesForm(forms.ModelForm):
    registration_updates = forms.BooleanField(
        label=_('Send me updates about events I have registered for'),
        help_text='You will always receive these, they are not optional.',
        initial=True,
        disabled=True,
        required=False,
    )

    def save(self):
        with transaction.atomic():
            user = super().save()

            for (attr, consent_name) in CONSENT_PREFS.items():
                if attr in self.changed_data:
                    ConsentLog.log_consent(
                        user=user,
                        consent_name=consent_name,
                        value=getattr(user, attr),
                        form_field=self.fields[attr],
                    )

        return user

    class Meta:
        model = ArtaUser
        fields = ['registration_updates', *CONSENT_PREFS.keys()]
