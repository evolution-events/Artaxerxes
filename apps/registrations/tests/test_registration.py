import itertools
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError, OperationalError
from django.forms.models import model_to_dict
from django.test import TestCase, skipUnlessDBFeature
from django.urls import reverse
from parameterized import parameterized, parameterized_class

from apps.core.models import ConsentLog
from apps.events.tests.factories import EventFactory
from apps.people.models import Address, EmergencyContact, MedicalDetails
from apps.people.tests.factories import AddressFactory, ArtaUserFactory, EmergencyContactFactory, MedicalDetailsFactory

from ..models import Registration, RegistrationFieldValue
from ..services import RegistrationStatusService
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestRegistration(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew")

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


class TestRegistrationForm(TestCase):
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

        # And posting again should still redirect to the first step, without creating a new Registration or modifying
        # the status.
        response = self.client.post(start_url)
        self.assertRedirects(response, first_step_url)
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


class TestConstraints(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    @skipUnlessDBFeature('supports_table_check_constraints')
    def test_registration_has_timestamp(self):
        reg = RegistrationFactory(registered=True)
        reg.registered_at = None
        with self.assertRaises(IntegrityError):
            reg.save()

    @skipUnlessDBFeature('supports_partial_indexes')
    def test_one_registration_per_user_per_event(self):
        reg = RegistrationFactory(registered=True)
        with self.assertRaises(IntegrityError):
            RegistrationFactory(registered=True, user=reg.user, event=reg.event)

    @skipUnlessDBFeature('supports_partial_indexes')
    def test_one_registration_per_user_per_event_cancelled(self):
        reg = RegistrationFactory(cancelled=True)
        RegistrationFactory(registered=True, user=reg.user, event=reg.event)
