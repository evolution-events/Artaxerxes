from django import forms

from apps.people.models import ArtaUser


class SignupFormBase(forms.Form):
    """ Custom signup form. The allauth default forms (local account and social account) will derive from this.  """

    # TODO: When implementing social accounts, we should probably pre-fill these fields with data from user, as
    # populated by the social provider if available.
    first_name = ArtaUser._meta.get_field('first_name').formfield(required=True)
    last_name = ArtaUser._meta.get_field('last_name').formfield(required=True)

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
