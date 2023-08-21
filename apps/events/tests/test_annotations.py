from datetime import datetime, timedelta, timezone

from django.test import TestCase

from apps.people.tests.factories import ArtaUserFactory, GroupFactory
from apps.registrations.models import Registration
from apps.registrations.tests.factories import (RegistrationFactory, RegistrationFieldFactory,
                                                RegistrationFieldOptionFactory)

from ..models import Event
from .factories import EventFactory


class TestOpenedAnnotations(TestCase):
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
        # Public, open date reached, closed date not reached
        EventFactory(title='future_public_open_now_with_close', starts_in_days=7, public=True,
                     registration_opens_in_days=-1, registration_closes_in_days=5)
        # Public, close date reached
        EventFactory(title='future_public_closed_again', starts_in_days=7, public=True,
                     registration_opens_in_days=-8, registration_closes_in_days=-3)

        # Public, admit_immediately=False, no open date yet
        EventFactory(title='future_pending_public_closed', starts_in_days=7, public=True, admit_immediately=False)
        # Public, admit_immediately=False, open date scheduled
        EventFactory(title='future_pending_public_opens_soon', starts_in_days=7, public=True, admit_immediately=False,
                     registration_opens_in_days=1)
        # Public, admit_immediately=False, open date reached
        EventFactory(title='future_pending_public_open_now', starts_in_days=7, public=True, admit_immediately=False,
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
        # Corner case with close date after start date, should still close at start date
        EventFactory(title='past_public_closes_after_start', starts_in_days=-1, public=True,
                     registration_opens_in_days=-7, registration_closes_in_days=1)

        # This is how past events should usually be: public and with an open date in the past before the start date,
        # with or without closing date
        EventFactory(title='past_public_open_now', starts_in_days=-7, public=True,
                     registration_opens_in_days=-8)
        EventFactory(title='past_public_closed_again', starts_in_days=-6, public=True,
                     registration_opens_in_days=-8, registration_closes_in_days=-7)

        # Check uniqueness of titles. Cannot use unittests asserts since we are not in a testcase yet.
        events = list(Event.objects.all())
        titles = {e.title for e in events}
        assert(len(titles) == len(events))

        cls.organizer = ArtaUserFactory(last_name="Organizer")
        cls.organizer_group = GroupFactory(users=[cls.organizer])
        for e in events:
            e.organizer_group = cls.organizer_group
            e.save()

        cls.admin = ArtaUserFactory(is_superuser=True, last_name="Admin")

    def assertEventsWithTitles(self, events, titles):
        """ Assert the titles of the given events exactly match the given titles. """
        self.assertSetEqual({e.title for e in events}, titles)

    def test_is_visible(self):
        """ Test is_visible annotation. """
        for user in (None, self.organizer):
            with self.subTest(user=user):
                annotated = Event.objects.for_user(None)
                visible = set(annotated.filter(is_visible=True))
                self.assertEventsWithTitles(visible, {
                    'future_public_open_now',
                    'future_public_open_now_with_close',
                    'future_public_closed_again',
                    'future_public_opens_soon',
                    'future_pending_public_open_now',
                    'future_pending_public_opens_soon',
                    'past_public_opens_soon',
                    'past_public_open_now',
                    'past_public_closed_again',
                    'past_public_closes_after_start',
                })

    def test_organizer_can_preview(self):
        """ Test can_preview annotation for organizers. """
        for user in (self.organizer, self.admin):
            with self.subTest(user=user):
                annotated = Event.objects.for_user(user)
                can_preview = set(annotated.filter(can_preview=True))
                self.assertEventsWithTitles(can_preview, {
                    'future_hidden_closed',
                    'future_hidden_open_now',
                    'future_hidden_opens_soon',
                    'future_public_closed',
                    'future_pending_public_opens_soon',
                    'future_pending_public_closed',
                })

    def test_others_can_preview(self):
        """ Test can_preview annotation for other users. """
        annotated = Event.objects.for_user(None)
        can_preview = set(annotated.filter(can_preview=True))
        self.assertEventsWithTitles(can_preview, set())

    def test_registration_is_open(self):
        """ Test registration_is_open annotation. """
        annotated = Event.objects.for_user(None)
        is_open = set(annotated.filter(registration_is_open=True))
        self.assertEventsWithTitles(is_open, {
            'future_public_open_now',
            'future_public_open_now_with_close',
            'future_pending_public_open_now',
        })

    def test_registration_has_closed(self):
        """ Test registration_has_closed annotation. """
        annotated = Event.objects.for_user(None)
        has_closed = set(annotated.filter(registration_has_closed=True))
        self.assertEventsWithTitles(has_closed, {
            'future_public_closed_again',
            'past_hidden_closed',
            'past_hidden_opens_soon',
            'past_hidden_open_now',
            'past_public_closed',
            'past_public_opens_soon',
            'past_public_open_now',
            'past_public_closed_again',
            'past_public_closes_after_start',
        })

    def test_preregistration_is_open(self):
        """ Test preregistration_is_open annotation. """
        annotated = Event.objects.for_user(None)
        is_open = set(annotated.filter(preregistration_is_open=True))
        self.assertEventsWithTitles(is_open, {
            'future_public_opens_soon',
        })

    def test_registration_and_preregistration(self):
        """ Tests that no events are open for registration *and* preregistration. """
        annotated = Event.objects.for_user(None)
        registration_and_preregistration = set(annotated.filter(
            registration_is_open=True,
            preregistration_is_open=True,
        ))

        self.assertEqual(registration_and_preregistration, set())


class TestIsFullAnnotation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = ArtaUserFactory()
        cls.event = EventFactory(full=False)
        cls.field = RegistrationFieldFactory(event=cls.event)
        cls.ingroup = GroupFactory(name='ingroup', users=[cls.user])
        cls.outgroup = GroupFactory(name='outgroup', users=[])

    def setUp(self):
        # Ensure any changes to the event are undone in the object as well.
        self.event.refresh_from_db()

    def check_is_full(self, is_full):
        """ Helper that checks whether is_full returns the right value. """
        annotated = Event.objects.for_user(self.user).get(pk=self.event.pk)
        self.assertEqual(annotated.is_full, is_full)

    def test_event_full(self):
        """ Test that an event with full=True is full. """
        self.event.full = True
        self.event.save()
        self.check_is_full(True)

    def test_event_full_option_available(self):
        """ Test that an event with full=True is full, even when a non-full option exists. """
        self.event.full = True
        self.event.save()
        RegistrationFieldOptionFactory(field=self.field)

        self.check_is_full(True)

    def test_one_option_full(self):
        """ Test that one full option does not make the event full. """
        RegistrationFieldOptionFactory(field=self.field, full=False)
        RegistrationFieldOptionFactory(field=self.field, full=True)

        self.check_is_full(False)

    def test_all_options_full(self):
        """ Test that all full options makes the event full. """
        RegistrationFieldOptionFactory(field=self.field, full=True)
        RegistrationFieldOptionFactory(field=self.field, full=True)

        self.check_is_full(True)

    def test_all_options_full_and_non_full_field(self):
        """ Test that all full options makes the event full, even if another field has non-full options. """
        RegistrationFieldOptionFactory(field=self.field, full=True)
        RegistrationFieldOptionFactory(field=self.field, full=True)
        field2 = RegistrationFieldFactory(event=self.event)
        RegistrationFieldOptionFactory(field=field2, full=False)

        self.check_is_full(True)

    def test_nonfull_not_invited_option(self):
        """ Test that when your are not invited to the only non-full option, the event is full. """
        RegistrationFieldOptionFactory(field=self.field, full=True)
        RegistrationFieldOptionFactory(field=self.field, full=False, invite_only=self.outgroup)

        self.check_is_full(True)

    def test_nonfull_invited_option(self):
        """ Test that when your are invited to the only non-full option, the event is not full. """
        RegistrationFieldOptionFactory(field=self.field, full=True)
        RegistrationFieldOptionFactory(field=self.field, full=False, invite_only=self.ingroup)

        self.check_is_full(False)


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
        earlier = datetime.now(timezone.utc) - timedelta(seconds=1)
        RegistrationFactory(event=self.event, user=self.user, cancelled=True, created_at=earlier)
        reg = RegistrationFactory(event=self.event, user=self.user, cancelled=True)

        e = Event.objects.for_user(self.user, with_registration=True).get()
        self.assertEqual(e.registration, reg)
