from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized

from apps.people.tests.factories import ArtaUserFactory
from apps.registrations.models import Registration
from apps.registrations.tests.factories import RegistrationFactory

from ..models import Event
from .factories import EventFactory


class TestRegisteredEventsView(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Open is not scheduled yet, event is hidden while being prepared
        EventFactory(title='future_hidden_closed', starts_in_days=7, public=False)
        # This is a corner case: Open but hidden
        EventFactory(title='future_hidden_open_now', starts_in_days=7, public=False,
                     registration_opens_in_days=-1)
        # This is a realistic case: open is already scheduled, but event is still hidden while being prepared
        EventFactory(title='future_hidden_opens_soon', starts_in_days=7, public=False,
                     registration_opens_in_days=1)

        # Public, but no open date yet
        EventFactory(title='future_public_closed', starts_in_days=7, public=True)
        # Public, open date scheduled
        EventFactory(title='future_public_opens_soon', starts_in_days=7, public=True,
                     registration_opens_in_days=1)
        # Public, open date reached
        EventFactory(title='future_public_open_now', starts_in_days=7, public=True,
                     registration_opens_in_days=-1)

        # Public, event starts today
        EventFactory(title='future_public_open_now_starts_today', starts_in_days=0, public=True,
                     registration_opens_in_days=-1)

        # These are corner cases, past events should usually not be hidden, and have an opens at in the past
        EventFactory(title='past_hidden_closed', starts_in_days=-7, public=False)
        EventFactory(title='past_hidden_opens_soon', starts_in_days=-7, public=False,
                     registration_opens_in_days=1)
        EventFactory(title='past_hidden_open_now', starts_in_days=-7, public=False,
                     registration_opens_in_days=-8)
        EventFactory(title='past_public_closed', starts_in_days=-7, public=True)
        EventFactory(title='past_public_opens_soon', starts_in_days=-7, public=True,
                     registration_opens_in_days=1)

        # This is how past events should usually be: public and with an open date in the past before the start date
        EventFactory(title='past_public_open_now', starts_in_days=-7, public=True,
                     registration_opens_in_days=-8)

        # Check uniqueness of titles. Cannot use unittests asserts since we are not in a testcase yet.
        events = Event.objects.all()
        titles = {e.title for e in events}
        assert(len(titles) == len(events))

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    def get(self):
        """ Helper to request this view. """
        url = reverse('events:registered_events')
        with self.assertTemplateUsed('events/registered_events.html'):
            return self.client.get(url)

    def makeRegistrationsForEvents(self, titles, **kwargs):
        """ Make registrations for the event with the given titles and returns them. """
        return [
            RegistrationFactory(event=e, **kwargs)
            for e in Event.objects.filter(title__in=titles)
        ]

    def assertRegistrationsMatch(self, events, registrations):
        """ Assert that the registrations returned for the given events match the given registrations. """
        self.assertCountEqual(
            [e.registration for e in events],
            registrations,
        )

    def test_no_registrations(self):
        """ Check events without registrations do not show up. """
        response = self.get()
        self.assertCountEqual(response.context['events']['future'], [])
        self.assertCountEqual(response.context['events']['past'], [])

    @parameterized.expand((s,) for s in Registration.statuses.constants)
    def test_other_users_registrations(self, status):
        """ Check that other users' registrations do not show up. """

        self.makeRegistrationsForEvents(status=status, titles=[
            'future_public_open_now',
            'future_public_open_now_starts_today',
            'past_public_open_now',
            'past_public_closed',
        ])

        response = self.get()
        self.assertCountEqual(response.context['events']['future'], [])
        self.assertCountEqual(response.context['events']['past'], [])

    @parameterized.expand((s,) for s in Registration.statuses.FINALIZED)
    def test_finalized_registrations(self, status):
        """ Check that finalized registrations do show up. """
        # TODO: Decide how to handle non-public or closed events (with registrations) and include them here.
        future = self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'future_public_open_now',
        ])

        past = self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'future_public_open_now_starts_today',
            'past_public_open_now',
            'past_public_closed',
        ])

        response = self.get()
        self.assertRegistrationsMatch(response.context['events']['future'], future)
        self.assertRegistrationsMatch(response.context['events']['past'], past)

    @parameterized.expand((s,) for s in Registration.statuses.FINALIZED)
    def test_finalized_replaces_cancelled(self, status):
        """ Check that finalized registrations replace earlier cancelled registrations. """
        self.makeRegistrationsForEvents(status=Registration.statuses.CANCELLED, titles=[
            'future_public_open_now',
            'past_public_open_now',
        ])

        future = self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'future_public_open_now',
        ])

        past = self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'past_public_open_now',
        ])

        response = self.get()
        self.assertRegistrationsMatch(response.context['events']['future'], future)
        self.assertRegistrationsMatch(response.context['events']['past'], past)

    @parameterized.expand((s,) for s in Registration.statuses.DRAFT)
    def test_draft_does_not_replace_cancelled(self, status):
        """ Check that draft registrations do not replace earlier cancelled registrations. """

        future = self.makeRegistrationsForEvents(user=self.user, status=Registration.statuses.CANCELLED, titles=[
            'future_public_open_now',
        ])

        past = self.makeRegistrationsForEvents(user=self.user, status=Registration.statuses.CANCELLED, titles=[
            'past_public_open_now',
        ])

        self.makeRegistrationsForEvents(status=status, titles=[
            'future_public_open_now',
            'past_public_open_now',
        ])

        response = self.get()
        self.assertRegistrationsMatch(response.context['events']['future'], future)
        self.assertRegistrationsMatch(response.context['events']['past'], past)

    @parameterized.expand((s,) for s in Registration.statuses.DRAFT)
    def test_draft_registrations(self, status):
        """ Check that draft registrations do not show up. """
        self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'future_public_open_now',
            'future_public_open_now_starts_today',
            'past_public_open_now',
            'past_public_closed',
        ])

        response = self.get()
        self.assertCountEqual(response.context['events']['future'], [])
        self.assertCountEqual(response.context['events']['past'], [])
