from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
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
        future = []
        past = []
        for e in self.object_list:
            if e.start_date > date.today():
                future.append(e)
            else:
                past.append(e)

        future.reverse()

        kwargs['events'] = {
            'past': past,
            'future': future,
        }
        return super().get_context_data(**kwargs)


class OrganizedEventsList(LoginRequiredMixin, ListView):
    """ List of events a user has organizer access to. """

    template_name = 'events/organized_events.html'
    allow_empty = False
    model = Event
    ordering = '-start_date'

    def get_queryset(self):
        return super().get_queryset().for_organizer(self.request.user).annotate(
            num_registered=Count('registrations', filter=Q(registrations__status=Registration.statuses.REGISTERED)),
            num_waitinglist=Count('registrations', filter=Q(registrations__status=Registration.statuses.WAITINGLIST)),
            num_cancelled=Count('registrations', filter=Q(registrations__status=Registration.statuses.CANCELLED)),
        )

    def get_context_data(self, **kwargs):
        counts = Registration.objects.values_list('status').annotate(count=Count('status'))
        kwargs['counts'] = {status.id: count for status, count in counts}
        return super().get_context_data(**kwargs)
