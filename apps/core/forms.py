import reversion
from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.core.models import ConsentLog
from apps.people.models import ArtaUser


class SignupFormBase(forms.Form):
    """ Custom signup form. The allauth default forms (local account and social account) will derive from this.  """

    # TODO: When implementing social accounts, we should probably pre-fill these fields with data from user, as
    # populated by the social provider if available.
    first_name = ArtaUser._meta.get_field('first_name').formfield(required=True)
    last_name = ArtaUser._meta.get_field('last_name').formfield(required=True)
    consent_announcements = ArtaUser._meta.get_field('consent_announcements').formfield()

    def signup(self, request, user):
        with reversion.create_revision():
            reversion.set_user(user)
            reversion.set_comment(_("Account created via frontend."))

            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.consent_announcements = self.cleaned_data['consent_announcements']
            user.save()

        if user.consent_announcements:
            ConsentLog.objects.create(
                user=user,
                action=ConsentLog.actions.CONSENTED,
                consent_name='email_announcements',
                consent_description=self.fields['consent_announcements'].help_text,
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

            if 'consent_announcements' in self.changed_data:
                if user.consent_announcements:
                    action = ConsentLog.actions.CONSENTED
                else:
                    action = ConsentLog.actions.WITHDRAWN

                ConsentLog.objects.create(
                    user=user,
                    action=action,
                    consent_name='email_announcements',
                    consent_description=self.fields['consent_announcements'].help_text,
                )

        return user

    class Meta:
        model = ArtaUser
        fields = ['registration_updates', 'consent_announcements']
