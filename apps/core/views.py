# from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def organisation_info_view(request):
    """ Show some information about the organisation. """
    return render(request, 'core/organisation_info.html')
