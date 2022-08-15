import itertools
from datetime import datetime, timedelta, timezone

from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized

from apps.people.tests.factories import ArtaUserFactory, GroupFactory, MedicalDetailsFactory
from apps.registrations.models import Registration
from apps.registrations.tests.factories import (RegistrationFactory, RegistrationFieldFactory,
                                                RegistrationFieldOptionFactory)

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
        # Public, close date reached
        EventFactory(title='future_public_closed_again', starts_in_days=7, public=True,
                     registration_opens_in_days=-8, registration_closes_in_days=-3)

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

        # This is how past events should usually be: public and with an open date in the past before the start date,
        # with or without closing date
        EventFactory(title='past_public_open_now', starts_in_days=-7, public=True,
                     registration_opens_in_days=-8)
        EventFactory(title='past_public_closed_again', starts_in_days=-6, public=True,
                     registration_opens_in_days=-8, registration_closes_in_days=-7)

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

    def makeRegistrationsForEvents(self, titles=None, **kwargs):
        """ Make registrations for the event with the given titles and returns them. """
        events = Event.objects.all()
        if titles is not None:
            events = events.filter(title__in=titles)
        return [RegistrationFactory(event=e, **kwargs) for e in events]

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

        self.makeRegistrationsForEvents(status=status)
        response = self.get()
        self.assertCountEqual(response.context['events']['future'], [])
        self.assertCountEqual(response.context['events']['past'], [])

    @parameterized.expand((s,) for s in Registration.statuses.FINALIZED)
    def test_finalized_registrations(self, status):
        """ Check that finalized registrations do show up. """
        # TODO: Decide how to handle non-public or closed events (with registrations) and include them here.
        future = self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'future_public_open_now',
            'future_public_closed_again',
            'future_public_open_now_starts_today',
        ])

        past = self.makeRegistrationsForEvents(user=self.user, status=status, titles=[
            'past_public_open_now',
            'past_public_closed',
            'past_public_closed_again',
        ])

        response = self.get()
        self.assertRegistrationsMatch(response.context['events']['future'], future)
        self.assertRegistrationsMatch(response.context['events']['past'], past)

    @parameterized.expand((s,) for s in Registration.statuses.FINALIZED)
    def test_finalized_replaces_cancelled(self, status):
        """ Check that finalized registrations replace earlier cancelled registrations. """
        earlier = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.makeRegistrationsForEvents(status=Registration.statuses.CANCELLED, created_at=earlier, titles=[
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
        self.makeRegistrationsForEvents(user=self.user, status=status)

        response = self.get()
        self.assertCountEqual(response.context['events']['future'], [])
        self.assertCountEqual(response.context['events']['past'], [])


class TestOrganizedEventsList(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizers = ArtaUserFactory.create_batch(2)
        cls.other_organizers = ArtaUserFactory.create_batch(2)

        cls.organizer_group = GroupFactory(users=cls.organizers)
        cls.other_group = GroupFactory(users=cls.other_organizers)

        # Add two events with organizers, one with other organizers and one without
        cls.events_for_organizers = EventFactory.create_batch(2, organizer_group=cls.organizer_group)
        cls.event_for_others = EventFactory(organizer_group=cls.other_group)
        cls.other_event = EventFactory()

    def get(self, status_code=200):
        """ Helper to request this view. """
        response = self.client.get(reverse('events:organized_events'))
        self.assertEqual(response.status_code, status_code)
        if status_code == 200:
            self.assertTemplateUsed(response, 'events/organized_events.html')
        return response

    def test_events_shown(self):
        """ Check that the list of events shown is correct """

        self.client.force_login(self.organizers[0])

        response = self.get()

        qs = response.context['event_list']
        # Pass transform to prevent string conversion (TODO: remove in Django 3.2)
        self.assertQuerysetEqual(qs, self.events_for_organizers, transform=lambda o: o, ordered=False)

    def test_no_organizer(self):
        """ Check that you get an error when you are no organizer. """

        self.client.force_login(ArtaUserFactory())
        self.get(status_code=404)

    def test_not_logged_in(self):
        """ Check that you are redirected when not logged in. """

        self.get(status_code=302)


class TestEventRegistrationInfo(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizers = ArtaUserFactory.create_batch(2)
        cls.other_organizers = ArtaUserFactory.create_batch(2)

        cls.organizer_group = GroupFactory(users=cls.organizers)
        cls.other_group = GroupFactory(users=cls.other_organizers)

        # Add two events with organizers, one with other organizers and one without
        cls.events_for_organizers = EventFactory.create_batch(2, organizer_group=cls.organizer_group)
        cls.event_for_others = EventFactory(organizer_group=cls.other_group)
        cls.other_event = EventFactory()

    views = [
        ('events:registration_forms', 'events/printable/registration_forms.html', 'text/html; charset=utf-8'),
        ('events:printable_registration_forms', 'events/printable/registration_forms.html', 'application/pdf'),
        ('events:kitchen_info', 'events/printable/kitchen_info.html', 'text/html; charset=utf-8'),
        ('events:printable_kitchen_info', 'events/printable/kitchen_info.html', 'application/pdf'),
        ('events:safety_reference', 'events/printable/safety_info.html', 'text/html; charset=utf-8'),
        ('events:printable_safety_reference', 'events/printable/safety_info.html', 'application/pdf'),
        ('events:safety_info', 'events/printable/safety_info.html', 'text/html; charset=utf-8'),
        ('events:registrations_table', 'events/registrations_table.html', 'text/html; charset=utf-8'),
        ('events:registrations_table_download', None, 'application/vnd.oasis.opendocument.spreadsheet'),
    ]

    def get(self, view, template, content_type, event, status_code=200):
        """ Helper to request a view. """
        response = self.client.get(reverse(view, args=(event.pk,)))
        self.assertEqual(response.status_code, status_code)
        if status_code == 200:
            if template:
                self.assertTemplateUsed(response, template)
            self.assertEqual(response['Content-Type'], content_type)

        return response

    # TODO: Add actualy participants (with different variations of address/medical details set/unset) and test that all
    # views return the expected registrations (and no others, especially not of other events).
    @parameterized.expand(views)
    def test_correct_organizer(self, view, template, content_type):
        """ Check that you get no error when you are the organizer for the event. """

        self.client.force_login(self.organizers[0])
        e = self.events_for_organizers[0]
        self.get(view, template, content_type, e)

    @parameterized.expand(views)
    def test_other_organizer(self, view, template, content_type):
        """ Check that you get an error when you are only organizer for another event. """

        self.client.force_login(self.other_organizers[0])
        e = self.events_for_organizers[0]
        self.get(view, template, content_type, e, status_code=404)

    @parameterized.expand(views)
    def test_no_organizer(self, view, template, content_type):
        """ Check that you get an error when you are no organizer. """

        e = self.events_for_organizers[0]
        self.client.force_login(ArtaUserFactory())
        self.get(view, template, content_type, e, status_code=404)

    @parameterized.expand(views)
    def test_not_logged_in(self, view, template, content_type):
        """ Check that you are redirected when not logged in. """

        e = self.events_for_organizers[0]
        self.get(view, template, content_type, e, status_code=302)


class TestKitchenInfo(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = ArtaUserFactory()
        cls.organizer_group = GroupFactory(users=[cls.organizer])
        cls.event = EventFactory(organizer_group=cls.organizer_group)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type", allow_change_days=1)
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.npc = RegistrationFieldOptionFactory(field=cls.type, title="NPC")

        cls.food = RegistrationFieldFactory(event=cls.event, name="food", is_kitchen_info=True)
        cls.meat = RegistrationFieldOptionFactory(field=cls.food, title="meat")
        cls.vegetarian = RegistrationFieldOptionFactory(field=cls.food, title="veggie")

    def setUp(self):
        self.client.force_login(self.organizer)

    def get(self, expected_registrations):
        view = 'events:kitchen_info'
        response = self.client.get(reverse(view, args=(self.event.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/printable/kitchen_info.html')

        # Pass transform to prevent string conversion (TODO: remove in Django 3.2)
        self.assertQuerysetEqual(
            response.context['registration_list'],
            expected_registrations,
            ordered=False, transform=lambda o: o,
        )
        return response

    def test_registrations_with_info(self):
        """ Test that only registrations with info are included. """
        # Registration with allergy info (should be included)
        reg_allergy = RegistrationFactory(event=self.event, options=[self.player], registered=True)
        MedicalDetailsFactory(user=reg_allergy.user, food_allergies="foo")

        # Registration with empty allergy info (should be omitted)
        reg_empty_allergy = RegistrationFactory(event=self.event, options=[self.player], registered=True)
        MedicalDetailsFactory(user=reg_empty_allergy.user, food_allergies="")

        # Registration with kitchen info field (should be included, but inactive option omitted)
        reg_kitchen_field = RegistrationFactory(
            event=self.event, options=[self.player, self.vegetarian], inactive_options=[self.meat], registered=True)

        # Registration with neither (should be omitted)
        RegistrationFactory(event=self.event, options=[self.player], registered=True)

        response = self.get(expected_registrations=[reg_allergy, reg_kitchen_field])

        render_allergy, render_kitchen_field = response.context['registration_list'].order_by('created_at')
        self.assertEqual([render_allergy.pk, render_kitchen_field.pk], [reg_allergy.pk, reg_kitchen_field.pk])

        self.assertEqual(render_allergy.kitchen_options, [])
        kitchen_fields = [option.field for option in render_kitchen_field.kitchen_options]
        self.assertEqual(kitchen_fields, [self.food])

    @parameterized.expand(itertools.product(Registration.statuses.constants))
    def test_only_registered(self, status):
        """ Test that only REGISTERED registrations are included. """

        reg = RegistrationFactory(event=self.event, options=[self.player, self.vegetarian], status=status)

        expected_registrations = [reg] if status.REGISTERED else []
        self.get(expected_registrations)
