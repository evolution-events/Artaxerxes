from django import forms
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.db import transaction
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView

from .models import ArtaUser


@method_decorator(permission_required('auth.change_group'), name='dispatch')
class AddUsersToGroupView(FormView):
    model = ArtaUser
    admin_site = None  # Filled by __init__
    template_name = 'people/admin/add_users_to_group.html'

    class SelectGroupForm(forms.Form):
        group = forms.ModelChoiceField(
            queryset=Group.objects.all(),
            label="Add users to this group",
        )
    form_class = SelectGroupForm

    def __init__(self, admin_site):
        self.admin_site = admin_site

    def get_context_data(self, **kwargs):
        kwargs.update(self.admin_site.each_context(self.request))
        kwargs.update({
            'opts': self.model._meta,
            'users': ArtaUser.objects.filter(pk__in=self.get_userids()),
        })
        return super().get_context_data(**kwargs)

    def get_userids(self):
        return map(int, self.kwargs['userids'].split(','))

    def form_valid(self, form):
        with transaction.atomic():
            # TODO: Use reversion, but this probably requires registering Group with reversion, which did not work
            # right away, so was left for later
            group = form.cleaned_data['group']
            group.user_set.add(*self.get_userids())

        return redirect('admin:auth_group_change', group.pk)
