# from django.shortcuts import render
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def event_index_view(request):
        """
        Landing page for events.

        (TODO: really needed?)
        """
        return render(request, 'events/index.html', {'user': request.user})


@login_required
def event_list_view(request):
    """
    List of all events that people can register for.
    """
    # TODO: actually filter or select on events one can register for
    events = Event.objects.all()

    return render(request, 'events/list.html', {'user': request.user, 'events': events})
