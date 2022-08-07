from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature

from apps.people.tests.factories import ArtaUserFactory, GroupFactory
from apps.registrations.models import Registration
from apps.registrations.tests.factories import RegistrationFactory

from ..models import Event
from .factories import EventFactory, SeriesFactory


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

    def test_for_organizer(self):
        organizers = ArtaUserFactory.create_batch(2)
        other_users = ArtaUserFactory.create_batch(2)

        organizer_group = GroupFactory(users=organizers)
        other_group = GroupFactory(users=other_users)

        # Add two events with organizers, one with other organizers and one without
        events = EventFactory.create_batch(2, organizer_group=organizer_group)
        EventFactory(organizer_group=other_group)
        EventFactory()

        for user in organizers:
            qs = Event.objects.for_organizer(user)
            # Pass transform to prevent string conversion (TODO: remove in Django 3.2)
            self.assertQuerysetEqual(qs, events, transform=lambda o: o, ordered=False)


class TestConstraints(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    @skipUnlessDBFeature('supports_table_check_constraints')
    def test_has_email_or_series_fail(self):
        with self.assertRaises(IntegrityError):
            EventFactory(email='')

    def test_has_email_or_series_ok(self):
        e = EventFactory()
        e.email = ''
        e.series = SeriesFactory()
        e.save()
