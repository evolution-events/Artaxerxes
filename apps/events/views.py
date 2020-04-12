import collections
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Event


@login_required
def event_list_view(request):
    """ List of all events that people can register or have registered for. """
    events = Event.objects.for_user(request.user, with_registration=True).filter(is_visible=True)

    def group(e):
        if e.start_date > date.today():
            if e.registration and e.registration.status.ACTIVE:
                return 'active'
            else:
                return 'future'
        else:
            if e.registration and e.registration.status.REGISTERED:
                return 'history'
            else:
                return None

    grouped = collections.defaultdict(list)
    for e in events:
        grouped[group(e)].append(e)

    return render(request, 'events/registered_events.html', {'user': request.user, 'events': grouped})
