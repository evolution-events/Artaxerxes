from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized

from apps.people.tests.factories import ArtaUserFactory, GroupFactory
from apps.registrations.tests.factories import RegistrationFactory

from .factories import EventFactory


# TODO: This code is largely copied from apps.events.tests.test_views.TestEventRegistrationInfo
# Can we reduce common code?
class TestOrganizerViews(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizers = ArtaUserFactory.create_batch(2)
        cls.other_organizers = ArtaUserFactory.create_batch(2)

        cls.organizer_group = GroupFactory(users=cls.organizers)
        cls.other_group = GroupFactory(users=cls.other_organizers)

        # Add two events with organizers, one with other organizers and one without
        cls.event_for_organizers = EventFactory(organizer_group=cls.organizer_group)
        cls.event_for_others = EventFactory(organizer_group=cls.other_group)
        cls.event_without_organizers = EventFactory()

        cls.registration_for_organizers = RegistrationFactory(event=cls.event_for_organizers)
        cls.registration_for_others = RegistrationFactory(event=cls.event_for_others)
        cls.registration_without_organizers = RegistrationFactory(event=cls.event_without_organizers)

    views = [
        ('registrations:registration_payment_details', 'registrations/registration_payment_details.html',
         'text/html; charset=utf-8'),
    ]

    def get(self, view, template, content_type, reg, status_code=200):
        """ Helper to request a view. """
        response = self.client.get(reverse(view, args=(reg.pk,)))
        self.assertEqual(response.status_code, status_code)
        if status_code == 200:
            if template:
                self.assertTemplateUsed(response, template)
            self.assertEqual(response['Content-Type'], content_type)

        return response

    # TODO: Test that actually the right registration details are returned
    @parameterized.expand(views)
    def test_correct_organizer(self, view, template, content_type):
        """ Check that you get no error when you are the organizer for the event. """

        self.client.force_login(self.organizers[0])
        r = self.registration_for_organizers
        self.get(view, template, content_type, r)

    @parameterized.expand(views)
    def test_other_organizer(self, view, template, content_type):
        """ Check that you get an error when you are only organizer for another event. """

        self.client.force_login(self.other_organizers[0])
        reg = self.registration_for_organizers
        self.get(view, template, content_type, reg, status_code=404)

    @parameterized.expand(views)
    def test_no_organizer(self, view, template, content_type):
        """ Check that you get an error when you are no organizer. """

        reg = self.registration_for_organizers
        self.client.force_login(ArtaUserFactory())
        self.get(view, template, content_type, reg, status_code=404)

    @parameterized.expand(views)
    def test_not_logged_in(self, view, template, content_type):
        """ Check that you are redirected when not logged in. """

        reg = self.registration_for_organizers
        self.get(view, template, content_type, reg, status_code=302)
