import collections
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Event


@login_required
def event_index_view(request):
    """ Landing page for events.

    (TODO: really needed?)
    """
    return render(request, 'events/index.html', {'user': request.user})


@login_required
def event_list_view(request):
    """ List of all events that people can register for. """
    events = Event.objects.for_user(request.user, with_registration_status=True).filter(is_visible=True)

    def group(e):
        if e.start_date > date.today():
            if e.registration_status and e.registration_status.ACTIVE:
                return 'active'
            else:
                return 'future'
        else:
            if e.registration_status and e.registration_status.REGISTERED:
                return 'history'
            else:
                return None

    grouped = collections.defaultdict(list)
    for e in events:
        grouped[group(e)].append(e)

    return render(request, 'events/list.html', {'user': request.user, 'events': grouped})
