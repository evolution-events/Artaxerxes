from datetime import datetime, timedelta, timezone

from django.db.models import Q
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
        # These are a corner cases: Open (for public and/or invitees) but hidden
        EventFactory(title='future_hidden_open_now', starts_in_days=7, public=False,
                     registration_opens_in_days=-1)
        EventFactory(title='future_hidden_invite_only_open_now', starts_in_days=7, public=False,
                     invitee_registration_opens_in_days=-1)
        EventFactory(title='future_hidden_invitees_open_now_public_open_now', starts_in_days=7, public=False,
                     invitee_registration_opens_in_days=-2, registration_opens_in_days=-1)
        EventFactory(title='future_hidden_invitees_open_now', starts_in_days=7, public=False,
                     invitee_registration_opens_in_days=-1, registration_opens_in_days=1)
        # These are realistic cases: open is already scheduled, but event is still hidden while being prepared
        EventFactory(title='future_hidden_opens_soon', starts_in_days=7, public=False,
                     registration_opens_in_days=1)
        EventFactory(title='future_hidden_invite_only_opens_soon', starts_in_days=7, public=False,
                     invitee_registration_opens_in_days=1)
        EventFactory(title='future_hidden_invitee_opens_soon', starts_in_days=7, public=False,
                     invitee_registration_opens_in_days=1, registration_opens_in_days=2)

        # Public, but no open date yet
        EventFactory(title='future_public_closed', starts_in_days=7, public=True)
        # Public, open date scheduled
        EventFactory(title='future_public_opens_soon', starts_in_days=7, public=True,
                     registration_opens_in_days=1)
        EventFactory(title='future_public_invite_only_opens_soon', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=1)
        EventFactory(title='future_public_invitee_opens_soon_public_opens_soon', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=1, registration_opens_in_days=2)
        # Public, open date reached
        EventFactory(title='future_public_open_now', starts_in_days=7, public=True,
                     registration_opens_in_days=-1)
        EventFactory(title='future_public_invite_only_open_now', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=-1)
        EventFactory(title='future_public_invitee_open_now_public_open_now', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=-2, registration_opens_in_days=-1)
        # Public, open date reached for invitees, not public
        EventFactory(title='future_public_invitee_open_now_public_opens_soon', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=-1, registration_opens_in_days=1)

        # Public, open date reached, closed date not reached
        EventFactory(title='future_public_open_now_with_close', starts_in_days=7, public=True,
                     registration_opens_in_days=-1, registration_closes_in_days=5)
        EventFactory(title='future_public_invite_only_open_now_with_close', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=-1, registration_closes_in_days=5)
        EventFactory(title='future_public_invitee_open_now_public_open_now_with_close', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=-2, registration_opens_in_days=-1,
                     registration_closes_in_days=5)
        EventFactory(title='future_public_invitee_open_now_public_opens_soon_with_close', starts_in_days=7,
                     public=True, invitee_registration_opens_in_days=-1, registration_opens_in_days=1,
                     registration_closes_in_days=5)

        # Public, close date reached
        EventFactory(title='future_public_closed_again', starts_in_days=7, public=True,
                     registration_opens_in_days=-8, registration_closes_in_days=-3)
        EventFactory(title='future_public_invite_only_open_now_closed_again', starts_in_days=7, public=True,
                     invitee_registration_opens_in_days=-8, registration_closes_in_days=-3)
        EventFactory(title='future_public_invitee_open_now_public_open_now_closed_again', starts_in_days=7,
                     public=True, invitee_registration_opens_in_days=-8, registration_opens_in_days=-7,
                     registration_closes_in_days=-3)
        # Corner case: close date reached before open
        EventFactory(title='future_public_invitee_open_now_public_opens_soon_closed_again', starts_in_days=7,
                     public=True, invitee_registration_opens_in_days=-8, registration_opens_in_days=1,
                     registration_closes_in_days=-3)

        # Public, admit_immediately=False, no open date yet
        EventFactory(title='future_pending_public_closed', starts_in_days=7, public=True, admit_immediately=False)
        # Public, admit_immediately=False, open date scheduled
        EventFactory(title='future_pending_public_opens_soon', starts_in_days=7, public=True, admit_immediately=False,
                     registration_opens_in_days=1)
        EventFactory(title='future_pending_public_invite_only_opens_soon', starts_in_days=7, public=True,
                     admit_immediately=False, invitee_registration_opens_in_days=1)
        # Public, admit_immediately=False, open date reached
        EventFactory(title='future_pending_public_open_now', starts_in_days=7, public=True, admit_immediately=False,
                     registration_opens_in_days=-1)
        EventFactory(title='future_pending_public_invite_only_open_now', starts_in_days=7, public=True,
                     admit_immediately=False, invitee_registration_opens_in_days=-1)

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
        EventFactory(title='past_public_invite_only_open_now', starts_in_days=-7, public=True,
                     invitee_registration_opens_in_days=-8)
        EventFactory(title='past_public_closed_again', starts_in_days=-6, public=True,
                     registration_opens_in_days=-8, registration_closes_in_days=-7)
        EventFactory(title='past_public_invite_only_closed_again', starts_in_days=-6, public=True,
                     invitee_registration_opens_in_days=-8, registration_closes_in_days=-7)

        # Check uniqueness of titles. Cannot use unittests asserts since we are not in a testcase yet.
        events = list(Event.objects.all())
        titles = {e.title for e in events}
        assert(len(titles) == len(events))

        cls.organizer = ArtaUserFactory(last_name="Organizer")
        cls.organizer_group = GroupFactory(users=[cls.organizer])

        cls.invitee = ArtaUserFactory(last_name="Invitee")
        cls.invitee_group = GroupFactory(users=[cls.invitee])

        for e in events:
            e.organizer_group = cls.organizer_group
            # This is only used when invitee_opens_at is also set, but it should be ok to just always set it
            e.invitee_group = cls.invitee_group
            e.save()

        cls.admin = ArtaUserFactory(is_superuser=True, last_name="Admin")
        cls.user = ArtaUserFactory(last_name="User")
        cls.all_users = (cls.user, cls.invitee, cls.admin, cls.organizer)

    def assertEventsWithTitles(self, events, titles, additional_titles=None):
        """ Assert the titles of the given events exactly match the given titles. """
        self.assertSetEqual({e.title for e in events}, titles | (additional_titles or set()))

    def annotation_test_helper(self, users, filter, for_all, for_invitees=frozenset(), for_non_invitees=frozenset()):
        for user in users:
            with self.subTest(user=user):
                annotated = Event.objects.for_user(user)
                filtered = set(annotated.filter(filter))
                if user == self.invitee:
                    expected = for_all | for_invitees
                else:
                    expected = for_all | for_non_invitees
                self.assertEventsWithTitles(filtered, expected)

    def test_is_visible(self):
        """ Test is_visible annotation. """
        self.annotation_test_helper(
            (None, self.organizer, self.invitee), Q(is_visible=True),
            for_all={
                'future_public_opens_soon',
                'future_public_open_now',
                'future_public_invitee_opens_soon_public_opens_soon',
                'future_public_invitee_open_now_public_open_now',
                'future_public_invitee_open_now_public_opens_soon',
                'future_public_open_now_with_close',
                'future_public_invitee_open_now_public_open_now_with_close',
                'future_public_invitee_open_now_public_opens_soon_with_close',
                'future_public_closed_again',
                'future_public_invitee_open_now_public_open_now_closed_again',
                'future_public_invitee_open_now_public_opens_soon_closed_again',
                'future_pending_public_opens_soon',
                'future_pending_public_open_now',
                'past_public_opens_soon',
                'past_public_open_now',
                'past_public_closed_again',
                'past_public_closes_after_start',
            }, for_invitees={
                'future_public_invite_only_opens_soon',
                'future_public_invite_only_open_now',
                'future_public_invite_only_open_now_with_close',
                'future_public_invite_only_open_now_closed_again',
                'future_pending_public_invite_only_opens_soon',
                'future_pending_public_invite_only_open_now',
                'past_public_invite_only_open_now',
                'past_public_invite_only_closed_again',
            },
        )

    def test_organizer_can_preview(self):
        """ Test can_preview annotation for organizers. """
        self.annotation_test_helper(
            (self.organizer, self.admin), Q(can_preview=True),
            for_all={
                'future_hidden_closed',
                'future_hidden_open_now',
                'future_hidden_invite_only_open_now',
                'future_hidden_invitees_open_now_public_open_now',
                'future_hidden_invitees_open_now',
                'future_hidden_opens_soon',
                'future_hidden_invite_only_opens_soon',
                'future_hidden_invitee_opens_soon',
                'future_public_closed',
                'future_public_invite_only_opens_soon',
                'future_public_invite_only_open_now',
                'future_public_invite_only_open_now_with_close',
                'future_pending_public_opens_soon',
                'future_pending_public_closed',
                'future_pending_public_invite_only_opens_soon',
                'future_pending_public_invite_only_open_now',
            },
        )

    def test_others_can_preview(self):
        """ Test can_preview annotation for other users. """
        self.annotation_test_helper((self.user, self.invitee), Q(can_preview=True), frozenset())

    def test_registration_is_open(self):
        """ Test registration_is_open annotation. """
        self.annotation_test_helper(
            self.all_users, Q(registration_is_open=True),
            for_all={
                'future_public_open_now',
                'future_public_invitee_open_now_public_open_now',
                'future_public_open_now_with_close',
                'future_public_invitee_open_now_public_open_now_with_close',
                'future_pending_public_open_now',
            }, for_invitees={
                'future_public_invite_only_open_now',
                'future_public_invitee_open_now_public_opens_soon',
                'future_public_invite_only_open_now_with_close',
                'future_public_invitee_open_now_public_opens_soon_with_close',
                'future_pending_public_invite_only_open_now',
            },
        )

    def test_registration_has_closed(self):
        """ Test registration_has_closed annotation. """
        self.annotation_test_helper(
            self.all_users, Q(registration_has_closed=True),
            for_all={
                'future_public_closed_again',
                'future_public_invitee_open_now_public_open_now_closed_again',
                'future_public_invitee_open_now_public_opens_soon_closed_again',
                'future_public_invite_only_open_now_closed_again',
                'past_hidden_closed',
                'past_hidden_opens_soon',
                'past_hidden_open_now',
                'past_public_closed',
                'past_public_opens_soon',
                'past_public_closes_after_start',
                'past_public_open_now',
                'past_public_invite_only_open_now',
                'past_public_closed_again',
                'past_public_invite_only_closed_again',
            },
        )

    def test_preregistration_is_open(self):
        """ Test preregistration_is_open annotation. """
        self.annotation_test_helper(
            self.all_users, Q(preregistration_is_open=True),
            for_all={
                'future_public_opens_soon',
                'future_public_invitee_opens_soon_public_opens_soon',
            }, for_invitees={
                'future_public_invite_only_opens_soon',
            }, for_non_invitees={
                'future_public_invitee_open_now_public_opens_soon',
                'future_public_invitee_open_now_public_opens_soon_with_close',
            },
        )

    def test_registration_and_preregistration(self):
        """ Tests that no events are open for registration *and* preregistration. """
        self.annotation_test_helper(self.all_users, Q(registration_is_open=True) & Q(preregistration_is_open=True),
                                    frozenset())


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


class TestForUserAnnotationRegression(TestCase):
    def test_duplicate_results(self):
        """ This checks for a Django limitation related to duplicating results when a join is involved. """

        # This is https://code.djangoproject.com/ticket/10060 that was worked around in for_user, so check the
        # workaround does not break
        group = GroupFactory(users=ArtaUserFactory.create_batch(2))
        EventFactory(invitee_group=group, organizer_group=group)
        events = Event.objects.all().for_user(None)
        self.assertEqual(len(events), 1)
