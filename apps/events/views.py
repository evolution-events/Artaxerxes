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
