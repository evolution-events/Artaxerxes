from django.conf import settings
from django.test.runner import DiscoverRunner


class CustomRunner(DiscoverRunner):
    """
    Helper class to allow code to detect that it is ran inside a unittest.

    It seems a custom runner (and using the TEST_RUNNER django setting) is the most reliabe way to detect this. Taken
    from https://stackoverflow.com/a/15890649/740048
    """

    def __init__(self, *args, **kwargs):
        settings.IN_UNITTEST = True
        super().__init__(*args, **kwargs)
