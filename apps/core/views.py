import collections
from datetime import date

import reversion
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, TemplateView, UpdateView, View

from apps.events.models import Event
from apps.registrations.models import Registration

from .forms import EmailPreferencesForm


class PrivacyPolicy(RedirectView):
    url = 'https://www.evolution-events.nl/algemeen/?pg=privacy#english'


class HouseRules(RedirectView):
    url = 'https://www.evolution-events.nl/algemeen/?pg=huisregels#english'


class Dashboard(LoginRequiredMixin, View):
    def get(self, request):
        events = Event.objects.for_user(
            request.user,
            with_registration=True,
        ).filter(
            ~Q(registration_has_closed=True) | Q(registration_status__in=Registration.statuses.FINALIZED),
            start_date__gt=date.today(),
            is_visible=True,
        ).order_by(
            'start_date',
        )

        def group(e):
            if e.registration and e.registration.status.ACTIVE:
                return 'active'
            elif e.registration_is_open or e.preregistration_is_open:
                return 'open'
            else:
                return 'upcoming'

        grouped = collections.defaultdict(list)
        for e in events:
            grouped[group(e)].append(e)

        context = {
            'user': request.user,
            'events': grouped,
        }
        return render(request, 'core/dashboard.html', context)


class PracticalInfo(LoginRequiredMixin, TemplateView):
    template_name = 'core/practical_info.html'


# No need to log in to see this page
class AboutArta(TemplateView):
    template_name = 'core/about_this_system.html'


class EmailPreferences(LoginRequiredMixin, UpdateView):
    template_name = "core/email_preferences.html"
    form_class = EmailPreferencesForm
    success_url = reverse_lazy('core:email_prefs')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        with reversion.create_revision():
            reversion.set_user(self.request.user)
            reversion.set_comment(_("Email notification preferences updated via frontend."))
            res = super().form_valid(form)

            # Sanity check, to ensure the reversion/consent user are consistent with the user just updated
            if self.object != self.request.user:
                raise SuspiciousOperation("EmailPreferencesForm should be submitted for yourself only")
        return res
