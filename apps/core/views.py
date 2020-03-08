import collections
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import View

from apps.events.models import Event


class RegistrationsDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        events = Event.objects.for_user(request.user, with_registration=True).filter(is_visible=True)

        def group(e):
            if e.start_date > date.today():
                if e.registration.status and e.registration.status.ACTIVE:
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
        return render(request, 'core/how_does_it_work.html')
