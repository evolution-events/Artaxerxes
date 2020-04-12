import collections
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import RedirectView, View

from apps.events.models import Event


class PrivacyPolicyView(RedirectView):
    url = 'https://www.evolution-events.nl/algemeen/?pg=privacy#english'


class HouseRulesView(RedirectView):
    url = 'https://www.evolution-events.nl/algemeen/?pg=huisregels#english'


class RegistrationsDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        events = Event.objects.for_user(
            request.user,
            with_registration=True,
        ).filter(
            is_visible=True,
            start_date__gt=date.today(),
        )

        def group(e):
            if e.registration and e.registration.status.ACTIVE:
                return 'active'
            else:
                return 'future'

        grouped = collections.defaultdict(list)
        for e in events:
            grouped[group(e)].append(e)

        context = {
            'user': request.user,
            'events': grouped,
        }
        return render(request, 'core/dashboard.html', context)


@login_required
def practical_info_view(request):
    """ Show some information about the organisation, payments and policies. """
    return render(request, 'core/practical_info.html')


# No need to log in to see this page
class AboutArtaView(View):
    def get(self, request):
        return render(request, 'core/about_this_system.html')
