import collections
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import View

from apps.events.models import Event


class RegistrationsDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        events = Event.objects.for_user(request.user, with_registration_status=True).filter(is_visible=True)

        def group(e):
            if e.start_date > date.today():
                if e.registration_status and e.registration_status.ACTIVE:
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
def organisation_info_view(request):
    """ Show some information about the organisation. """
    return render(request, 'core/organisation_info.html')
