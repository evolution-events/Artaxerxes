import collections
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import RedirectView, TemplateView, View

from apps.events.models import Event


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
            is_visible=True,
            start_date__gt=date.today(),
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
