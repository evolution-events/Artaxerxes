from django.test import TestCase

from apps.registrations.models import Registration
from apps.registrations.tests.factories import RegistrationFactory

from ..models import Event
from .factories import EventFactory


class TestQueryset(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory()
        cls.event2 = EventFactory()

    def test_used_slots_for(self):
        """ Test the used_slots_for() query set method. """
        for e in (self.event, self.event2):
            for s in Registration.statuses.constants:
                RegistrationFactory(event=e, status=s)

        RegistrationFactory(event=self.event, registered=True)
        self.assertEqual(Event.objects.used_slots_for(self.event), 2)
