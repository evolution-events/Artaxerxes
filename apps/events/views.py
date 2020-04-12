from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView

from apps.registrations.models import Registration

from .models import Event


class RegisteredEventList(LoginRequiredMixin, TemplateView):
    """ List of all events that the current user is registred for. """

    template_name = 'events/registered_events.html'

    def get_context_data(self, **kwargs):
        registered_events = (
            Event.objects
            .for_user(self.request.user, with_registration=True)
            .filter(registration_status__in=Registration.statuses.FINALIZED)
        )

        events = {'future': [], 'past': []}
        for e in registered_events:
            if e.start_date > date.today():
                events['future'].append(e)
            else:
                events['past'].append(e)

        context = super().get_context_data(**kwargs)
        context.update({
            'user': self.request.user,
            'events': events,
        })
        return context
