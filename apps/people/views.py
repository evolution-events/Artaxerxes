# from django.shortcuts import render
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def main_index_view(request):
        """
        A welcoming page to the user

        TODO: dit willen we hier niet houden, maar we moeten even uitzoeken waar het wel heen moet
        """
        return render(request, 'core/home.html')


@login_required
def person_index_view(request):
        """
        A welcoming page to the user
        """
        return render(request, 'people/index.html', {'user': request.user})
