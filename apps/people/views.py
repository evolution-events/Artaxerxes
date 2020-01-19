# from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render



@login_required
def person_index_view(request):
    """Render a list of users."""
    return render(request, 'people/index.html', {'user': request.user})
