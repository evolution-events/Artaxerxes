from django.test import TestCase

from apps.people.tests.factories import ArtaUserFactory
from apps.registrations.models import Registration
from apps.registrations.tests.factories import RegistrationFactory

from ..models import Event
from .factories import EventFactory


class TestOpenedAnnotations(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Open is not scheduled yet, event is hidden while being prepared
        EventFactory(title='future_hidden_closed', start_days_from_now=7, public=False)
        # This is a corner case: Open but hidden
        EventFactory(title='future_hidden_open_now', start_days_from_now=7, public=False,
                     registration_opens_in_days=-1)
        # This is a realistic case: open is already scheduled, but event is still hidden while being prepared
        EventFactory(title='future_hidden_opens_soon', start_days_from_now=7, public=False,
                     registration_opens_in_days=1)

        # Public, but no open date yet
        EventFactory(title='future_public_closed', start_days_from_now=7, public=True)
        # Public, open date scheduled
        EventFactory(title='future_public_opens_soon', start_days_from_now=7, public=True,
                     registration_opens_in_days=1)
        # Public, open date reached
        EventFactory(title='future_public_open_now', start_days_from_now=7, public=True,
                     registration_opens_in_days=-1)

        # These are corner cases, past events should usually not be hidden, and have an opens at in the past
        EventFactory(title='past_hidden_closed', start_days_from_now=-7, public=False)
        EventFactory(title='past_hidden_opens_soon', start_days_from_now=-7, public=False,
                     registration_opens_in_days=1)
        EventFactory(title='past_hidden_open_now', start_days_from_now=-7, public=False,
                     registration_opens_in_days=-8)
        EventFactory(title='past_public_closed', start_days_from_now=-7, public=True)
        EventFactory(title='past_public_opens_soon', start_days_from_now=-7, public=True,
                     registration_opens_in_days=1)

        # This is how past events should usually be: public and with an open date in the past before the start date
        EventFactory(title='past_public_open_now', start_days_from_now=-7, public=True,
                     registration_opens_in_days=-8)

        # Check uniqueness of titles. Cannot use unittests asserts since we are not in a testcase yet.
        events = Event.objects.all()
        titles = {e.title for e in events}
        assert(len(titles) == len(events))

    def assertEventsWithTitles(self, events, titles):
        """ Assert the titles of the given events exactly match the given titles. """
        self.assertSetEqual({e.title for e in events}, titles)

    def test_is_visible(self):
        """ Test is_visible annotation. """
        annotated = Event.objects.for_user(None)
        visible = set(annotated.filter(is_visible=True))
        self.assertEventsWithTitles(visible, {
            'future_public_closed',
            'future_public_open_now',
            'future_public_opens_soon',
            'past_public_closed',
            'past_public_opens_soon',
            'past_public_open_now',
        })

    def test_registration_is_open(self):
        """ Test registration_is_open annotation. """
        annotated = Event.objects.for_user(None)
        is_open = set(annotated.filter(registration_is_open=True))
        self.assertEventsWithTitles(is_open, {
            'future_public_open_now',
        })

    def test_preregistration_is_open(self):
        """ Test preregistration_is_open annotation. """
        annotated = Event.objects.for_user(None)
        is_open = set(annotated.filter(preregistration_is_open=True))
        self.assertEventsWithTitles(is_open, {
            'future_public_opens_soon',
            'future_public_closed',
        })

    def test_registration_and_preregistration(self):
        """ Tests that no events are open for registration *and* preregistration. """
        annotated = Event.objects.for_user(None)
        registration_and_preregistration = set(annotated.filter(
            registration_is_open=True,
            preregistration_is_open=True,
        ))

        self.assertEqual(registration_and_preregistration, set())


class TestRegistrationAnnotation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory()
        cls.user = ArtaUserFactory()

    def test_single_registration(self):
        """ A single registration should always be returned, regardless of its status. """
        reg = RegistrationFactory(event=self.event, user=self.user, registered=True)

        for status in Registration.statuses.constants:
            reg.status = status
            reg.save()

            e = Event.objects.for_user(self.user, with_registration=True).get()
            self.assertEqual(e.registration, reg)

    def test_two_registrations(self):
        """ With two registrations, the non-cancelled one should always be returned. """
        RegistrationFactory(event=self.event, user=self.user, cancelled=True)
        reg = RegistrationFactory(event=self.event, user=self.user, registered=True)

        for status in Registration.statuses.constants:
            if status != Registration.statuses.CANCELLED:
                reg.status = status
                reg.save()

                e = Event.objects.for_user(self.user, with_registration=True).get()
                self.assertEqual(e.registration, reg)

    def test_two_cancelled_registrations(self):
        """ With two cancelled registrations, the later one should be returned. """
        RegistrationFactory(event=self.event, user=self.user, cancelled=True)
        reg = RegistrationFactory(event=self.event, user=self.user, cancelled=True)

        e = Event.objects.for_user(self.user, with_registration=True).get()
        self.assertEqual(e.registration, reg)
