from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.registrations.models import Registration

from .models import Event


@login_required
def event_list_view(request):
    """ List of all events that people can register or have registered for. """

    registered_events = (
        Event.objects
        .for_user(request.user, with_registration=True)
        .filter(registration_status__in=Registration.statuses.FINALIZED)
    )

    events = {'future': [], 'past': []}
    for e in registered_events:
        if e.start_date > date.today():
            events['future'].append(e)
        else:
            events['past'].append(e)

    return render(request, 'events/registered_events.html', {'user': request.user, 'events': events})
