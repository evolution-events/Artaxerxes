from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.list import ListView

from apps.registrations.models import Registration

from .models import Event


class RegisteredEventList(LoginRequiredMixin, ListView):
    """ List of all events that the current user is registered for. """

    template_name = 'events/registered_events.html'
    model = Event
    ordering = '-start_date'

    def get_queryset(self):
        return (
            super().get_queryset()
            .for_user(self.request.user, with_registration=True)
            .filter(registration_status__in=Registration.statuses.FINALIZED)
        )

    def get_context_data(self, **kwargs):
        events = {'future': [], 'past': []}
        for e in self.object_list:
            if e.start_date > date.today():
                events['future'].append(e)
            else:
                events['past'].append(e)

        events['future'].reverse()

        context = super().get_context_data(**kwargs)
        context.update({
            'user': self.request.user,
            'events': events,
        })
        return context
