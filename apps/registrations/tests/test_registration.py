import itertools
import re
import time
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from unittest import mock, skip

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import OperationalError
from django.forms.models import model_to_dict
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from parameterized import parameterized, parameterized_class
from reversion.models import Revision
from with_asserts.mixin import AssertHTMLMixin

from apps.core.models import ConsentLog
from apps.events.models import Event
from apps.events.tests.factories import EventFactory
from apps.people.models import Address, ArtaUser, EmergencyContact, MedicalDetails
from apps.people.tests.factories import AddressFactory, ArtaUserFactory, EmergencyContactFactory, MedicalDetailsFactory

from ..models import Registration, RegistrationField, RegistrationFieldValue
from ..services import RegistrationStatusService
from ..views import FinalCheck
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestRegistration(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew")

        cls.section = RegistrationFieldFactory(
            event=cls.event, name="section", depends=cls.player, field_type=RegistrationField.types.SECTION,
        )

        cls.gender = RegistrationFieldFactory(event=cls.event, name="gender", depends=cls.player)
        cls.option_m = RegistrationFieldOptionFactory(field=cls.gender, title="M", slots=2)
        cls.option_f = RegistrationFieldOptionFactory(field=cls.gender, title="F", slots=2)

        cls.origin = RegistrationFieldFactory(event=cls.event, name="origin", depends=cls.player)
        cls.option_nl = RegistrationFieldOptionFactory(field=cls.origin, title="NL", slots=2)
        cls.option_intl = RegistrationFieldOptionFactory(field=cls.origin, title="INTL", slots=2)

    def incomplete_registration_helper(
        self, empty_field=None, with_emergency_contact=True, with_address=True, options=True,
        exception=ValidationError,
    ):
        if options is True:
            options = [self.player, self.option_m, self.option_nl]
        reg = RegistrationFactory(event=self.event, preparation_in_progress=True, options=options)

        if with_emergency_contact:
            EmergencyContactFactory(user=reg.user)
        if with_address:
            AddressFactory(user=reg.user)
        # MedicalDetails is optional, so no need to create it

        if empty_field:
            setattr(reg.user, empty_field, '')
            reg.user.save()

        if exception:
            with self.assertRaises(exception):
                RegistrationStatusService.preparation_completed(reg)
        else:
            RegistrationStatusService.preparation_completed(reg)

        reg.refresh_from_db()
        if exception:
            self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        else:
            self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)

    def test_missing_first_name(self):
        """ Check that a missing first name prevents completing preparation """
        self.incomplete_registration_helper(empty_field='first_name')

    def test_missing_last_name(self):
        """ Check that a missing last name prevents completing preparation """
        self.incomplete_registration_helper(empty_field='first_name')

    def test_missing_address(self):
        """ Check that a missing address prevents completing preparation """
        self.incomplete_registration_helper(with_address=False)

    def test_missing_emergency_contacts(self):
        """ Check that a missing emergency contacts prevent completing preparation """
        self.incomplete_registration_helper(with_emergency_contact=False)

    def test_missing_options(self):
        """ Check that missing options prevent completing preparation """
        self.incomplete_registration_helper(options=[])

    def test_partial_options(self):
        """ Check that incomplete options prevent completing preparation """
        self.incomplete_registration_helper(options=[self.player])

    def test_optional_options(self):
        """ Check that a omitting an optional option does not prevent completing preparation """
        self.incomplete_registration_helper(options=[self.crew], exception=None)

    def test_complete(self):
        """ Check that a complete registration can be completed """
        self.incomplete_registration_helper(exception=None)

    def test_register_until_option_full(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        for _i in range(2):
            reg = RegistrationFactory(
                event=e, preparation_complete=True,
                options=[self.player, self.option_m, self.option_nl],
            )
            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=[self.player, self.option_m, self.option_nl],
        )
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

    def test_register_until_event_full(self):
        """ Register until the event slots are taken and the next registration ends up on the waiting list. """
        e = self.event
        e.refresh_from_db()
        e.slots = 3
        e.save()

        for _i in range(2):
            reg = RegistrationFactory(
                event=e, preparation_complete=True,
                options=[self.player, self.option_m, self.option_nl],
            )
            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        # Two more registrations with different options to prevent triggering option slot limits
        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_f, self.option_intl])
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_f, self.option_intl])
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

    def test_register_twice_race_condition(self):
        """ Finalize *the same* registration twice with specific timing, regression test. """
        e = self.event
        e.refresh_from_db()
        e.slots = 1
        e.save()

        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_f, self.option_intl])
        reg_clone = Registration.objects.get(pk=reg.pk)

        now = timezone.now()

        # Finalize the registration just before finalize_registration enters the transaction. This should *not* run
        # inside the services' transaction, after the lock, since that would deadlock (that would need threading and
        # more coordination (that would need threading and more coordination).
        # TODO: Can we write this more concise?
        def before_transaction(*args, **kwargs):
            reg_clone.status = Registration.statuses.REGISTERED
            reg_clone.registered_at = now
            reg_clone.save()

            # Let the original function also run
            return mock.DEFAULT

        with mock.patch(
            'django.db.transaction.atomic',
            side_effect=before_transaction,
            wraps=transaction.atomic,
        ):
            with self.subTest("Should raise validationError"):
                with self.assertRaises(ValidationError):
                    RegistrationStatusService.finalize_registration(reg)

        reg.refresh_from_db()
        with self.subTest("Should not change status"):
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        with self.subTest("Should not change timestamp"):
            self.assertEqual(reg.registered_at, now)

    @skip("Conflict check disabled until improved")
    def test_register_two_events(self):
        """ Check that you can only register for one event. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration
        reg = RegistrationFactory(event=e, registered=True)

        # Causes second registration to be refused
        reg2 = RegistrationFactory(user=reg.user, event=e2, preparation_complete=True)
        with self.subTest("Should refuse registration"):
            with self.assertRaises(ValidationError):
                RegistrationStatusService.finalize_registration(reg2)
        with self.subTest("Should not change status"):
            self.assertTrue(reg2.status.PREPARATION_COMPLETE)

    def test_register_second_after_waitinglist(self):
        """ Check that you can still register for a second event after a waitinglist registration. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration on the waitinglist
        reg = RegistrationFactory(event=e, waiting_list=True)

        # Does not prevent another registration
        reg2 = RegistrationFactory(user=reg.user, event=e2, preparation_complete=True)
        RegistrationStatusService.finalize_registration(reg2)
        self.assertTrue(reg2.status.REGISTERED)

    def test_event_admit_immediately_false(self):
        """ Check that admit_immediately=False on an event produces a pending registration, regardless of slots """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.slots = 3
        e.save()

        for _i in range(4):
            reg = RegistrationFactory(
                event=e, preparation_complete=True,
                options=[self.player, self.option_m, self.option_nl],
            )

            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.PENDING)

    def test_option_admit_immediately_true(self):
        """ Check that admit_immediately=True on a selected option has precedence over the event """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.slots = 3
        e.save()

        self.crew.refresh_from_db()
        self.crew.admit_immediately = True
        self.crew.save()

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=[self.crew, self.option_m, self.option_nl],
        )

        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    def test_other_option_admit_immediately_true(self):
        """ Check that admit_immediately=True on a non-selected option has no precedence over the event """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.slots = 3
        e.save()

        self.crew.refresh_from_db()
        self.crew.admit_immediately = True
        self.crew.save()

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=[self.player, self.option_m, self.option_nl],
        )

        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.PENDING)

    @skipUnlessDBFeature('has_select_for_update')
    def test_finalize_locks(self):
        reg = RegistrationFactory(
            event=self.event, preparation_complete=True,
            options=[self.player, self.option_m, self.option_nl],
        )
        with CaptureQueriesContext(connection) as queries:
            RegistrationStatusService.finalize_registration(reg)
        with self.subTest("Must use SAVEPOINT"):
            # This ensures a transaction is started
            self.assertRegex(queries[0]["sql"], "^SAVEPOINT ")
        with self.subTest("Must lock event"):
            # This ensures that FOR UPDATE is used and that *only* the event is locked (i.e. no joins)
            match = ' FROM {table} WHERE {table}.{id_field} = {id} FOR UPDATE$'.format(
                table=re.escape(connection.ops.quote_name(Event._meta.db_table)),
                id_field=re.escape(connection.ops.quote_name(Event._meta.pk.column)),
                id=self.event.id,
            )
            self.assertRegex(queries[1]["sql"], match)
        with self.subTest("Must lock user"):
            # This ensures that FOR UPDATE is used and that *only* the event is locked (i.e. no joins)
            match = ' FROM {table} WHERE {table}.{id_field} = {id} FOR UPDATE$'.format(
                table=re.escape(connection.ops.quote_name(ArtaUser._meta.db_table)),
                id_field=re.escape(connection.ops.quote_name(ArtaUser._meta.pk.column)),
                id=reg.user.id,
            )
            self.assertRegex(queries[2]["sql"], match)


class TestRegistrationForm(TestCase, AssertHTMLMixin):
    registration_steps = (
        'registrations:step_registration_options',
        'registrations:step_personal_details',
        'registrations:step_medical_details',
        'registrations:step_emergency_contacts',
        'registrations:step_final_check',
    )

    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)
        cls.gender = RegistrationFieldFactory(event=cls.event, name="gender")
        cls.option_m = RegistrationFieldOptionFactory(field=cls.gender, title="M", slots=2)
        cls.option_f = RegistrationFieldOptionFactory(field=cls.gender, title="F", slots=2)

        cls.origin = RegistrationFieldFactory(event=cls.event, name="origin")
        cls.option_nl = RegistrationFieldOptionFactory(field=cls.origin, title="NL", slots=2)
        cls.option_intl = RegistrationFieldOptionFactory(field=cls.origin, title="INTL", slots=2)

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    def assertFinalizeAllowed(self, response):
        self.assertHTML(response, 'input[name="agree"]')
        self.assertHTML(response, 'button[type="submit"]')

    def assertFinalizeNotAllowed(self, response, waiting=False):
        self.assertNotHTML(response, 'input[name="agree"]')
        self.assertNotHTML(response, 'input[type="submit"]')

    def test_full_registration(self):
        """ Run through an entire registration flow. """
        e = self.event

        # Start step, should create a registration
        start_url = reverse('registrations:registration_start', args=(e.pk,))
        with self.assertTemplateUsed('registrations/registration_start.html'):
            self.client.get(start_url)

        response = self.client.post(start_url)
        reg = Registration.objects.get()
        next_url = reverse('registrations:step_registration_options', args=(reg.pk,))
        self.assertRedirects(response, next_url)

        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        self.assertEqual(reg.event, e)
        self.assertEqual(reg.user, self.user)

        # Options step, should create options
        with self.assertTemplateUsed('registrations/step_registration_options.html'):
            self.client.get(next_url)

        data = {
            self.gender.name: self.option_m.pk,
            self.origin.name: self.option_nl.pk,
        }
        response = self.client.post(next_url, data)
        next_url = reverse('registrations:step_personal_details', args=(reg.pk,))
        self.assertRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        gender, origin = RegistrationFieldValue.objects.all().order_by('field__name')
        self.assertEqual(gender.registration, reg)
        self.assertEqual(gender.field, self.gender)
        self.assertEqual(gender.option, self.option_m)
        self.assertEqual(origin.registration, reg)
        self.assertEqual(origin.field, self.origin)
        self.assertEqual(origin.option, self.option_nl)

        # Personal details step, should create Address and update user detail
        with self.assertTemplateUsed('registrations/step_personal_details.html'):
            self.client.get(next_url)

        data = {
            'user-first_name': 'foo',
            'user-last_name': 'bar',
            'address-phone_number': '+31101234567',
            'address-address': 'Some Street 123',
            'address-postalcode': '1234',
            'address-city': 'Town',
            'address-country': 'Country',
        }
        response = self.client.post(next_url, data)
        next_url = reverse('registrations:step_medical_details', args=(reg.pk,))
        self.assertRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, data['user-first_name'])
        self.assertEqual(self.user.last_name, data['user-last_name'])
        addr = Address.objects.get()
        self.assertEqual(addr.phone_number, data['address-phone_number'])
        self.assertEqual(addr.address, data['address-address'])
        self.assertEqual(addr.postalcode, data['address-postalcode'])
        self.assertEqual(addr.city, data['address-city'])
        self.assertEqual(addr.country, data['address-country'])

        # Medical details step, should create MedicalDetails
        with self.assertTemplateUsed('registrations/step_medical_details.html'):
            self.client.get(next_url)

        data = {
            'food_allergies': 'foo',
            'event_risks': 'bar',
            'consent': True,
        }
        response = self.client.post(next_url, data)
        next_url = reverse('registrations:step_emergency_contacts', args=(reg.pk,))
        self.assertRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        medical = MedicalDetails.objects.get()
        self.assertEqual(medical.food_allergies, data['food_allergies'])
        self.assertEqual(medical.event_risks, data['event_risks'])

        # Emergency contacts step, should create EmergencyContacts and update status
        with self.assertTemplateUsed('registrations/step_emergency_contacts.html'):
            self.client.get(next_url)

        data = {
            'emergency_contacts-TOTAL_FORMS': 2,
            'emergency_contacts-INITIAL_FORMS': 0,
            'emergency_contacts-0-contact_name': 'First name',
            'emergency_contacts-0-relation': 'First relation',
            'emergency_contacts-0-phone_number': '+31101234567',
            'emergency_contacts-0-remarks': 'First remarks',
            'emergency_contacts-1-contact_name': 'Second name',
            'emergency_contacts-1-relation': '',
            'emergency_contacts-1-phone_number': '+31107654321',
            'emergency_contacts-1-remarks': '',
        }
        response = self.client.post(next_url, data)
        next_url = reverse('registrations:step_final_check', args=(reg.pk,))
        self.assertRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)
        first, second = EmergencyContact.objects.all().order_by('id')
        self.assertEqual(first.user, self.user)
        self.assertEqual(first.contact_name, data['emergency_contacts-0-contact_name'])
        self.assertEqual(first.relation, data['emergency_contacts-0-relation'])
        self.assertEqual(first.phone_number, data['emergency_contacts-0-phone_number'])
        self.assertEqual(first.remarks, data['emergency_contacts-0-remarks'])
        self.assertEqual(second.user, self.user)
        self.assertEqual(second.contact_name, data['emergency_contacts-1-contact_name'])
        self.assertEqual(second.relation, data['emergency_contacts-1-relation'])
        self.assertEqual(second.phone_number, data['emergency_contacts-1-phone_number'])
        self.assertEqual(second.remarks, data['emergency_contacts-1-remarks'])

        # Final check, should update status
        with self.assertTemplateUsed('registrations/step_final_check.html'):
            self.client.get(next_url)

        response = self.client.post(next_url, {'agree': 1})
        next_url = reverse('registrations:registration_confirmation', args=(reg.pk,))
        self.assertRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    def test_registration_sends_email(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        reg = RegistrationFactory(event=e, user=self.user, preparation_complete=True,
                                  options=[self.option_m, self.option_nl])
        check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(reg.pk,))
        response = self.client.post(check_url, {'agree': 1})
        self.assertRedirects(response, confirm_url)

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [reg.user.email])
        self.assertEqual(mail.outbox[0].bcc, settings.BCC_EMAIL_TO)
        self.assertNotIn('waiting', mail.outbox[0].subject.lower())
        self.assertNotEqual(mail.outbox[0].subject.lower(), "")
        self.assertNotEqual(mail.outbox[0].body, '')

    def test_waitinglist_registration_sends_email(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        # Fill up some slots
        for _i in range(2):
            RegistrationFactory(event=e, registered=True, options=[self.option_m, self.option_nl])

        # Then register on the waiting list
        reg = RegistrationFactory(event=e, user=self.user, preparation_complete=True,
                                  options=[self.option_m, self.option_nl])
        check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(reg.pk,))
        response = self.client.post(check_url, {'agree': 1})
        self.assertRedirects(response, confirm_url)

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [reg.user.email])
        self.assertEqual(mail.outbox[0].bcc, settings.BCC_EMAIL_TO)
        self.assertIn('waiting', mail.outbox[0].subject.lower())
        self.assertEqual(len(mail.outbox), 1)

    def test_pending_registration_sends_email(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.pending_mail_text = "MARKERMARKERMARKER"
        e.save()

        reg = RegistrationFactory(event=e, user=self.user, preparation_complete=True,
                                  options=[self.option_m, self.option_nl])
        check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(reg.pk,))
        response = self.client.post(check_url, {'agree': 1})
        self.assertRedirects(response, confirm_url)

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.statuses.PENDING)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [reg.user.email])
        self.assertEqual(mail.outbox[0].bcc, settings.BCC_EMAIL_TO)
        self.assertNotIn('waiting', mail.outbox[0].subject.lower())
        self.assertNotEqual(mail.outbox[0].subject.lower(), "")
        self.assertIn(e.pending_mail_text, mail.outbox[0].body)
        self.assertEqual(len(mail.outbox), 1)

    def test_registration_start(self):
        e = self.event
        start_url = reverse('registrations:registration_start', args=(e.pk,))
        with self.assertTemplateUsed('registrations/registration_start.html'):
            self.client.get(start_url)

        # Send a post request to start registration procedure, this should created a new Registration and redirect to
        # the next step.
        response = self.client.post(start_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        reg = Registration.objects.get(user=self.user, event=e)
        first_step_url = reverse('registrations:step_registration_options', args=(reg.pk,))
        self.assertRedirects(response, first_step_url)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # Posting again should just redirect to the first step, and *not* create another Registration.
        response = self.client.post(start_url)
        self.assertRedirects(response, first_step_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # Getting should do the same
        response = self.client.get(start_url)
        self.assertRedirects(response, first_step_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # One preparation is complete, getting it should redirect to finalcheck
        reg.status = Registration.statuses.PREPARATION_COMPLETE
        reg.save()
        final_check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        response = self.client.get(start_url)
        self.assertRedirects(response, final_check_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)

        # And posting again should now redirect to final_check, without creating a new Registration or modifying the
        # status.
        response = self.client.post(start_url)
        self.assertRedirects(response, final_check_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)

    @parameterized.expand(registration_steps)
    def test_others_registration(self, viewname):
        """ Check that all registration steps fail with someone else's registration. """
        registration = RegistrationFactory(event=self.event)

        url = reverse(viewname, args=(registration.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    @parameterized.expand(registration_steps)
    def test_own_registration(self, viewname):
        """ Check that all registration steps load with your own registration. """
        registration = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)

        url = reverse(viewname, args=(registration.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Do not test POST, since that might not work reliably (e.g. the emergency contacts formset breaks for lack
        # of a management form).

    @parameterized.expand(registration_steps)
    def test_canceled_registration(self, viewname):
        """ Check that all registration steps reject a canceled registration """
        registration = RegistrationFactory(event=self.event, user=self.user, cancelled=True)

        url = reverse(viewname, args=(registration.pk,))
        # Follow, since some views redirect to final which 404s
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 404)

    @parameterized.expand(itertools.product(
        registration_steps,
        Registration.statuses.ACTIVE))
    def test_active_registration(self, viewname, status):
        """ Check that active registrations redirect to the registration completed page """
        registration = RegistrationFactory(event=self.event, user=self.user, status=status)

        url = reverse(viewname, args=(registration.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(registration.pk,))
        # Follow, since some views redirect to final which 404s
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, confirm_url)

        response = self.client.post(url, follow=True)
        self.assertRedirects(response, confirm_url)

    def test_not_logged_in(self):
        """ Check that the registration steps redirect when not logged in. """
        def test_view(view, args):
            url = reverse(view, args=args)
            with self.subTest(view=view, method='GET'):
                # Follow to redirect to the login page so we can check resolver_match
                response = self.client.get(url, follow=True)
                self.assertEqual(response.resolver_match.url_name, 'account_login')

            with self.subTest(view=view, method='POST'):
                # Follow to redirect to the login page so we can check resolver_match
                # This posts without data, since we should be redirected anyway
                response = self.client.post(url, follow=True)
                self.assertEqual(response.resolver_match.url_name, 'account_login')

        self.client.logout()
        registration = RegistrationFactory(event=self.event, user=self.user)

        test_view('registrations:registration_start', args=(self.event.pk,))
        for view in self.registration_steps:
            test_view(view, args=(registration.pk,))

    def test_registration_opens(self):
        """ Check that finalcheck is closed until the right time and then opens. """
        reg = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)
        opens_at = self.event.registration_opens_at
        before_opens_at = opens_at - timedelta(seconds=1)
        final_check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(reg.pk,))

        with mock.patch('django.utils.timezone.now', return_value=before_opens_at):
            response = self.client.get(final_check_url)
            self.assertFinalizeNotAllowed(response)
            self.assertFalse(response.context['event'].registration_is_open)

            response = self.client.post(final_check_url, {'agree': 1}, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['event'].registration_is_open)
            reg.refresh_from_db()
            self.assertFalse(reg.status.REGISTERED)

        with mock.patch('django.utils.timezone.now', return_value=opens_at):
            response = self.client.get(final_check_url)
            self.assertFinalizeAllowed(response)
            self.assertTrue(response.context['event'].registration_is_open)

            response = self.client.post(final_check_url, {'agree': 1})
            self.assertRedirects(response, confirm_url)
            reg.refresh_from_db()
            self.assertTrue(reg.status.REGISTERED)

    def test_registration_closes(self):
        """ Check that finalcheck regenerates a response after registration opens. """
        reg = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)
        start_date_midnight = timezone.make_aware(datetime.combine(self.event.start_date, dt_time.min))
        before_start_date = start_date_midnight - timedelta(seconds=1)
        final_check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(reg.pk,))

        with mock.patch('django.utils.timezone.now', return_value=before_start_date):
            response = self.client.get(final_check_url)
            self.assertFinalizeAllowed(response)
            self.assertTrue(response.context['event'].registration_is_open)

            response = self.client.post(final_check_url, {'agree': 1})
            self.assertRedirects(response, confirm_url)
            reg.refresh_from_db()
            self.assertTrue(reg.status.REGISTERED)

        reg.status = Registration.statuses.PREPARATION_COMPLETE
        reg.save()

        with mock.patch('django.utils.timezone.now', return_value=start_date_midnight):
            response = self.client.get(final_check_url, follow=True)
            self.assertEqual(response.status_code, 404)

            response = self.client.post(final_check_url, {'agree': 1}, follow=True)
            self.assertEqual(response.status_code, 404)
            reg.refresh_from_db()
            self.assertFalse(reg.status.REGISTERED)

    @parameterized.expand(registration_steps)
    @skip("Conflict check disabled until improved")
    def test_other_event_redirect_to_finalcheck(self, viewname):
        """ Check that all registration steps redirect to finalcheck when registered for another event. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)
        RegistrationFactory(user=self.user, event=e2, registered=True)
        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)

        url = reverse(viewname, args=(reg.pk,))
        conflict_url = reverse('registrations:conflicting_registrations', args=(reg.pk,))

        with self.subTest(method='GET'):
            response = self.client.get(url)
            self.assertRedirects(response, conflict_url)

        with self.subTest(method='GET'):
            response = self.client.post(url)
            self.assertRedirects(response, conflict_url)

    @skip("Conflict check disabled until improved")
    def test_register_two_events(self):
        """ Check that you can only register for one event. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration
        RegistrationFactory(user=self.user, event=e2, registered=True)

        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)
        final_check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        conflict_url = reverse('registrations:conflicting_registrations', args=(reg.pk,))

        # Causes second registration to be refused on GET
        response = self.client.get(final_check_url)
        with self.subTest(msg="Should redirect"):
            self.assertRedirects(response, conflict_url)

        # Causes second registration to be refused on POST
        response = self.client.post(final_check_url, {'agree': 1})
        with self.subTest(msg="Should redirect"):
            self.assertRedirects(response, conflict_url)
        with self.subTest(msg="Should not set status"):
            reg.refresh_from_db()
            self.assertTrue(reg.status.PREPARATION_COMPLETE)

    @skip("Conflict check disabled until improved")
    def test_register_two_events_between_view_and_service(self):
        """ Check that a second registration is refused, even when the first one happens late. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)
        other_reg = RegistrationFactory(user=self.user, event=e2, registered=True)

        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)
        final_check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        conflict_url = reverse('registrations:conflicting_registrations', args=(reg.pk,))

        # Make an existing registration just before the service finalizes. This should *not* run inside the services'
        # transaction, after the lock, since that would deadlock (that would need threading and more coordination (that
        # would need threading and more coordination).
        # TODO: Can we write this more concise?
        def before_finalize(*args, **kwargs):
            other_reg.status.REGISTERED = True
            other_reg.save()

            # Let the original function also run
            return mock.DEFAULT

        with mock.patch(
            'apps.registrations.services.RegistrationStatusService.finalize_registration',
            side_effect=before_finalize,
            wraps=RegistrationStatusService.finalize_registration,
        ):
            response = self.client.post(final_check_url, {'agree': 1})
            with self.subTest(msg="Should redirect"):
                self.assertRedirects(response, conflict_url)
            with self.subTest(msg="Should not set status"):
                reg.refresh_from_db()
                self.assertTrue(reg.status.PREPARATION_COMPLETE)

    def test_register_second_after_waiting_list(self):
        """ Check that you can still register for a second event after a waitinglist registration. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration on the waitinglist
        RegistrationFactory(user=self.user, event=e2, waiting_list=True)

        # Does not prevent another registration on GET
        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)
        final_check_url = reverse('registrations:step_final_check', args=(reg.pk,))
        confirm_url = reverse('registrations:registration_confirmation', args=(reg.pk,))
        response = self.client.get(final_check_url)
        with self.subTest(msg="Should show finalcheck with form"):
            self.assertTemplateUsed(response, FinalCheck.template_name)
            self.assertFinalizeAllowed(response)
        with self.subTest(msg="Should not set status"):
            self.assertTrue(reg.status.PREPARATION_COMPLETE)

        # Does not prevent another registration on POST
        response = self.client.post(final_check_url, {'agree': 1})
        with self.subTest(msg="Should redirect"):
            self.assertRedirects(response, confirm_url)
        with self.subTest(msg="Should set status"):
            reg.refresh_from_db()
            self.assertTrue(reg.status.REGISTERED)


# Parameterization produces TestMedicalConsentLog_0 and _1 class names
@parameterized_class([
    {'with_existing_details': False},
    {'with_existing_details': True},
])
class TestMedicalConsentLog(TestCase):
    info_fields = ('food_allergies', 'event_risks')
    consent_field = 'consent'
    consent_error = 'Consent required when any information is specified'
    consent_name = 'medical_data'

    @classmethod
    def setUpTestData(cls):
        cls.user = ArtaUserFactory()
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)
        cls.registration = RegistrationFactory(event=cls.event, user=cls.user)

        cls.form_url = reverse('registrations:step_medical_details', args=(cls.registration.pk,))
        cls.redirect_to = reverse('registrations:step_emergency_contacts', args=(cls.registration.pk,))

        if cls.with_existing_details:
            cls.details = MedicalDetailsFactory(user=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def assertResponse(self, response, success, should_exist, consent):
        if success is True:
            self.assertRedirects(response, self.redirect_to)
        elif success is False:
            self.assertFormError(response, 'form', self.consent_field, self.consent_error)

        if should_exist:
            details = MedicalDetails.objects.get(user=self.user)
        else:
            with self.assertRaises(MedicalDetails.DoesNotExist, msg="MedicalDetails should not exist"):
                MedicalDetails.objects.get(user=self.user)

        # Details should be unchanged if they existed beforehand and no consent was given or withdrawn
        if self.with_existing_details and consent is None:
            self.assertDictEqual(
                model_to_dict(self.details), model_to_dict(details),
                msg="MedicalDetails should be unchanged",
            )

        if consent is None:
            self.assertEqual(ConsentLog.objects.count(), 0, msg="No ConsentLog should be created")
        else:
            log = ConsentLog.objects.get()
            self.assertEqual(log.user, self.user)
            self.assertEqual(log.registration, self.registration)
            self.assertEqual(log.action, consent)
            self.assertEqual(log.consent_name, self.consent_name)

    def test_empty_form(self):
        """ Check that an empty form is allowed and produces no MedicalDetails or ConsentLog. """

        data = {field: '' for field in self.info_fields}
        response = self.client.post(self.form_url, data)

        consent = ConsentLog.actions.WITHDRAWN if self.with_existing_details else None
        self.assertResponse(response, success=True,
                            should_exist=False,
                            consent=consent)

    def test_empty_form_with_consent(self):
        """ Check that an empty form with consent is allowed but produces no MedicalDetails or ConsentLog. """

        data = {field: '' for field in self.info_fields}
        data[self.consent_field] = True
        response = self.client.post(self.form_url, data)

        self.assertResponse(response, success=True,
                            should_exist=False,
                            consent=ConsentLog.actions.WITHDRAWN if self.with_existing_details else None)

    @parameterized.expand(info_fields)
    def test_no_consent(self, non_empty_field):
        """ Check that a non-empty form without consent is rejected. """

        data = {field: '' for field in self.info_fields}
        data[non_empty_field] = 'xxx'
        data[self.consent_field] = False
        response = self.client.post(self.form_url, data)

        self.assertResponse(response, success=False,
                            should_exist=self.with_existing_details,
                            consent=None)

    @parameterized.expand(info_fields)
    def test_consent(self, non_empty_field):
        """ Check that a non-empty form with consent produces MedicalDetails and ConsentLog. """

        data = {field: '' for field in self.info_fields}
        data[non_empty_field] = 'xxx'
        data[self.consent_field] = True
        response = self.client.post(self.form_url, data)

        self.assertResponse(response, success=True,
                            should_exist=True,
                            consent=ConsentLog.actions.CONSENTED)

    def test_unchanged(self):
        """ Check that a form that does not change any fields is accepted but produces no ConsentLog. """
        if not self.with_existing_details:
            self.skipTest("Requires existing details")

        data = {field: getattr(self.details, field) for field in self.info_fields}
        data[self.consent_field] = True
        response = self.client.post(self.form_url, data)

        self.assertResponse(response, success=True,
                            should_exist=True,
                            consent=None)

    def test_consent_exception(self):
        """ Check that an exception during ConsentLog creation does not produce MedicalDetails. """
        data = {field: 'xxx' for field in self.info_fields}
        data[self.consent_field] = True

        with mock.patch('apps.core.models.consent_log.ConsentLog.save', side_effect=OperationalError):
            with self.assertRaises(OperationalError):
                self.client.post(self.form_url, data)

        self.assertResponse(response=None, success=None,
                            should_exist=self.with_existing_details,
                            consent=None)


class TestRevisions(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew")

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    def assertRevision(self, revision, models, fields=None):
        """ Assert that the given is correct and returns Version objects for the given models. """
        if fields is not None:
            split = revision.get_comment().split("fields changed: ", 1)
            self.assertEqual(len(split), 2, msg="Revision comment should contain changed fields list")
            changed_fields = split[1].split(", ")
            self.assertEqual(
                sorted(changed_fields), sorted(fields),
                msg="Revision comment changed fields should match expected fields",
            )
        self.assertEqual(revision.user, self.user)

        result = []
        versions = list(revision.version_set.all())
        for model in models:
            for i, version in enumerate(versions):
                if version.content_type.model_class() == model:
                    result.append(versions.pop(i))
                    break
            else:
                self.fail("Revision should contain version for {}".format(model))
        self.assertEqual(versions, [], msg="Revision should not contain extra versions")
        return result

    def assertFields(self, version, included=(), excluded=()):
        """ Assert that the give Version contains values for the right fields. """
        for f in included:
            self.assertIn(f, version.field_dict)

        for f in excluded:
            self.assertNotIn(f, version.field_dict)

    def test_registration_start(self):
        """ Check created revisions for start step. """
        # First post should create a single revision
        url = reverse('registrations:registration_start', args=(self.event.pk,))
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertRevision(Revision.objects.get(), [Registration])

        # Post again, should not create another revision
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

    def test_registration_options(self):
        """ Check created revisions for options step. """
        reg = RegistrationFactory(event=self.event, user=self.user)
        url = reverse('registrations:step_registration_options', args=(reg.pk,))

        # First post should create a single revision
        data = {self.type.name: self.player.pk}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        self.assertRevision(revision, [Registration, RegistrationFieldValue], [self.type.name])

        # Post again with unmodified data, should not create another revision
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

        # Post again with modified data, should create another revision
        data = {self.type.name: self.crew.pk}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        second_revision = Revision.objects.exclude(pk=revision.pk).get()
        self.assertRevision(second_revision, [Registration, RegistrationFieldValue], [self.type.name])

    def test_personal_details(self):
        """ Check created revisions for personal details step. """
        reg = RegistrationFactory(event=self.event, user=self.user)
        url = reverse('registrations:step_personal_details', args=(reg.pk,))

        # First post should create a single revision
        data = {
            'user-first_name': 'foo',
            'user-last_name': 'bar',
            'address-phone_number': '+31101234567',
            'address-address': 'Some Street 123',
            'address-postalcode': '1234',
            'address-city': 'Town',
            'address-country': 'Country',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        user_fields = [field.split("-")[1] for field in data if field.split("-")[0] == "user"]
        address_fields = [field.split("-")[1] for field in data if field.split("-")[0] == "address"]
        changed_fields = user_fields + address_fields
        changed_fields = address_fields + user_fields
        user_version, address_version = self.assertRevision(revision, [ArtaUser, Address], changed_fields)
        self.assertFields(user_version, included=user_fields)
        self.assertFields(address_version, excluded=address_fields)

        # Post again with unmodified data, should not create another revision
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

        # Post again with modified user data, should create another revision
        data['user-first_name'] = 'xxx'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        second_revision = Revision.objects.exclude(pk=revision.pk).get()
        self.assertRevision(second_revision, [ArtaUser, Address], ['first_name'])

        # Post again with modified address data, should create another revision
        data['address-city'] = 'xxx'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        third_revision = Revision.objects.exclude(pk__in=[revision.pk, second_revision.pk]).get()
        self.assertRevision(third_revision, [ArtaUser, Address], ['city'])

    def test_medical_details(self):
        """ Check created revisions for medical details step. """
        reg = RegistrationFactory(event=self.event, user=self.user)
        url = reverse('registrations:step_medical_details', args=(reg.pk,))

        # First post should create a single revision
        info_fields = ['food_allergies', 'event_risks']
        data = {
            info_fields[0]: 'foo',
            info_fields[1]: 'bar',
            'consent': True,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        _, medical_version = self.assertRevision(revision, [ArtaUser, MedicalDetails], data.keys())
        self.assertFields(medical_version, excluded=info_fields)

        # Post again with unmodified data, should not create another revision
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

        # Post again with modified data, should create another revision
        for f in info_fields:
            data[f] += 'modified'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        second_revision = Revision.objects.exclude(pk=revision.pk).get()
        _, medical_version = self.assertRevision(second_revision, [ArtaUser, MedicalDetails], info_fields)
        self.assertFields(medical_version, excluded=info_fields)

        # Post again with empty form, should create revision without MedicalDetails present
        data = {field: '' for field in data}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        third_revision = Revision.objects.exclude(pk__in=[revision.pk, second_revision.pk]).get()
        self.assertRevision(third_revision, [ArtaUser], data.keys())

    def test_emergency_contacts(self):
        """ Check created revisions for emergency contacts step. """
        # Create complete registration, to allow changing to PREPARATION_COMPLETED
        reg = RegistrationFactory(event=self.event, user=self.user, options=[self.player])
        AddressFactory(user=reg.user)
        # MedicalDetails is optional, so no need to create it

        url = reverse('registrations:step_emergency_contacts', args=(reg.pk,))

        # First post should create a one revision for the contacts and one for the registration
        info_fields = ['contact_name', 'relation', 'phone_number', 'remarks']
        data = {
            'emergency_contacts-TOTAL_FORMS': 2,
            'emergency_contacts-INITIAL_FORMS': 0,
            'emergency_contacts-0-contact_name': 'First name',
            'emergency_contacts-0-relation': 'First relation',
            'emergency_contacts-0-phone_number': '+31101234567',
            'emergency_contacts-0-remarks': 'First remarks',
            'emergency_contacts-1-contact_name': 'Second name',
            'emergency_contacts-1-relation': '',
            'emergency_contacts-1-phone_number': '+31107654321',
            'emergency_contacts-1-remarks': '',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        # First check the user/emergencycontacts revision
        emergency_contact_type = ContentType.objects.get_for_model(EmergencyContact)
        first_revision = Revision.objects.filter(version__content_type=emergency_contact_type).distinct().get()
        models = [ArtaUser, Address, EmergencyContact, EmergencyContact]
        _, _, *contact_versions = self.assertRevision(first_revision, models)
        for version in contact_versions:
            self.assertFields(version, excluded=info_fields)

        # Then check the registration revision
        registration_type = ContentType.objects.get_for_model(Registration)
        second_revision = Revision.objects.filter(version__content_type=registration_type).get()
        registration_version, _ = self.assertRevision(second_revision, [Registration, RegistrationFieldValue])
        self.assertFields(registration_version, included=['status'])

        # TODO: Check unmodified repost, which is a bit complicated since it requires adding emergency contact ids to
        # the form. Maybe a GET and submit that form would be easier?

    @skip("revision creation disabled for speed")
    def test_final_check(self):
        """ Check created revisions for final check step. """
        reg = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)

        url = reverse('registrations:step_final_check', args=(reg.pk,))

        # Post should create a one revision
        data = {'agree': True}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        (version,) = self.assertRevision(revision, [Registration])
        self.assertFields(version, included=['status'])


class TestCaching(TestCase):
    def setUp(self):
        self.event = EventFactory(registration_opens_in_days=-1, public=True)

        self.type = RegistrationFieldFactory(event=self.event, name="type")
        self.player = RegistrationFieldOptionFactory(field=self.type, title="Player")
        self.crew = RegistrationFieldOptionFactory(field=self.type, title="Crew")

        self.user = ArtaUserFactory()
        self.reg = RegistrationFactory(event=self.event, user=self.user, options=[self.player])
        self.address = AddressFactory(user=self.user)
        self.emergency_contacts = EmergencyContactFactory.create_batch(2, user=self.user)
        self.medical_details = MedicalDetailsFactory(user=self.user)

        self.final_check_url = reverse('registrations:step_final_check', args=(self.reg.pk,))

        self.client.force_login(self.user)

    def assertCache(self, response, changed):
        """ Assert that re-requesting the given response's request indeed returns a (not) modified status. """
        self.assertTrue(response.has_header('ETag'))
        # Repeat the same request without additional headers
        repeat = self.client.request(**response.request)
        self.assertHeaders(repeat, response, changed)

        # Then with If-None-Match
        request = {
            **response.request,
            'HTTP_IF_NONE_MATCH': response['ETag'],
        }

        second = self.client.request(**request)
        if changed:
            self.assertIn(second.status_code, [200, 302, 404])
        else:
            self.assertEqual(second.status_code, 304)
            self.assertEqual(second.content, b'')
        self.assertHeaders(second, response, changed)

    def assertHeaders(self, response, original, changed):
        # Other status codes (redirect when not logged in, 404) might bypass the ETag header addition, but 200 should
        # always have it.
        if response.status_code == 200:
            self.assertTrue(response.has_header('ETag'))

        if changed:
            if response.has_header('ETag'):
                self.assertNotEqual(response['ETag'], original['ETag'])
        else:
            self.assertEqual(response['ETag'], original['ETag'])

    def test_finalcheck_nochange(self):
        """ Check that finalcheck returns not-modified when nothing was changed. """
        response = self.client.get(self.final_check_url)
        self.assertCache(response, changed=False)

    def test_finalcheck_registration_opens(self):
        """ Check that finalcheck regenerates a response after registration opens. """
        # Make sure registration_opens_at is in the future (and newer than all updated_at timestamps)
        self.event.registration_opens_at = timezone.now() + timedelta(days=1)
        self.event.save()

        opens_at = self.event.registration_opens_at
        before_opens_at = opens_at - timedelta(seconds=1)

        response = self.client.get(self.final_check_url)
        with mock.patch('django.utils.timezone.now', return_value=before_opens_at):
            self.assertCache(response, changed=False)
            response = self.client.get(self.final_check_url)

        with mock.patch('django.utils.timezone.now', return_value=opens_at):
            self.assertCache(response, changed=True)

    @skip("Not implemented, see TODO in FinalCheck view")
    def test_finalcheck_registration_closes(self):
        """ Check that finalcheck regenerates a response after registration opens. """
        start_date_midnight = timezone.make_aware(datetime.combine(self.event.start_date, dt_time.min))
        before_start_date = start_date_midnight - timedelta(seconds=1)

        response = self.client.get(self.final_check_url)
        with mock.patch('django.utils.timezone.now', return_value=before_start_date):
            self.assertCache(response, changed=False)

        response = self.client.get(self.final_check_url)
        with mock.patch('django.utils.timezone.now', return_value=start_date_midnight):
            self.assertCache(response, changed=True)

    def test_finalcheck_data_changed(self):
        """ Check that finalcheck regenerates a resonse when models are changed. """

        objs = [
            self.event,
            self.user,
            self.address,
            self.medical_details,
            *self.emergency_contacts,
            self.reg,
            self.reg.options.first(),
            self.reg.options.first().option,
        ]

        for obj in objs:
            with self.subTest(data=repr(obj)):
                response = self.client.get(self.final_check_url)
                obj.save()
                self.assertCache(response, changed=True)

    def test_finalcheck_data_deleted(self):
        """ Check that finalcheck regenerates a resonse when models are deleted. """

        # In practice, probably only MedicalDetails or RegistrationOptionValue could be deleted (deleting an address
        # would invalidate the registration), but check everything anyway.
        objs = [
            self.emergency_contacts[0],
            self.reg.options.first(),
            self.address,
        ]

        for obj in objs:
            with self.subTest(data=repr(obj)):
                response = self.client.get(self.final_check_url)
                obj.delete()
                self.assertCache(response, changed=True)

    def test_finalcheck_registration_deleted(self):
        """ Check that finalcheck regenerates a resonse when the registration itself is deleted. """

        response = self.client.get(self.final_check_url)
        time.sleep(1)
        self.reg.delete()
        self.assertCache(response, changed=True)

    def test_finalcheck_logged_out(self):
        """ Check that finalcheck regenerates a response when the user logs out. """

        response = self.client.get(self.final_check_url)
        self.client.logout()
        self.assertCache(response, changed=True)

    def test_finalcheck_different_user(self):
        """ Check that finalcheck regenerates a response when the user logs in as another user. """

        other_user = ArtaUserFactory()
        # Let the registration updated_at be the largest of  all timestamps, to make an implementation that just takes
        # the max timestamp fail.
        self.reg.save()

        response = self.client.get(self.final_check_url)
        self.client.logout()
        self.client.force_login(other_user)
        self.assertCache(response, changed=True)

    def test_finalcheck_other_event(self):
        """ Check that finalcheck regenerates a response when the user registers for another event. """

        response = self.client.get(self.final_check_url)
        RegistrationFactory(user=self.user)
        self.assertCache(response, changed=True)
