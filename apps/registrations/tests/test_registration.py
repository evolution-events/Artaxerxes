import itertools

from django.conf import settings
from django.core import mail
from django.db.utils import IntegrityError
from django.forms.models import model_to_dict
from django.test import TestCase, skipUnlessDBFeature
from django.urls import reverse
from parameterized import parameterized, parameterized_class

from apps.core.models import ConsentLog
from apps.events.tests.factories import EventFactory
from apps.people.models import MedicalDetails
from apps.people.tests.factories import ArtaUserFactory, MedicalDetailsFactory

from ..models import Registration
from ..services import RegistrationStatusService
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestRegistration(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)
        gender = RegistrationFieldFactory(event=cls.event, name="gender")
        cls.option_m = RegistrationFieldOptionFactory(field=gender, title="M", slots=2)
        cls.option_f = RegistrationFieldOptionFactory(field=gender, title="F", slots=2)

        origin = RegistrationFieldFactory(event=cls.event, name="origin")
        cls.option_nl = RegistrationFieldOptionFactory(field=origin, title="NL", slots=2)
        cls.option_intl = RegistrationFieldOptionFactory(field=origin, title="INTL", slots=2)

    def test_register_until_option_full(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        for _i in range(2):
            reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_m, self.option_nl])
            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_m, self.option_nl])
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

    def test_register_until_event_full(self):
        """ Register until the event slots are taken and the next registration ends up on the waiting list. """
        e = self.event
        e.refresh_from_db()
        e.slots = 3
        e.save()

        for _i in range(2):
            reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_m, self.option_nl])
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
        gender = RegistrationFieldFactory(event=cls.event, name="gender")
        cls.option_m = RegistrationFieldOptionFactory(field=gender, title="M", slots=2)
        cls.option_f = RegistrationFieldOptionFactory(field=gender, title="F", slots=2)

        origin = RegistrationFieldFactory(event=cls.event, name="origin")
        cls.option_nl = RegistrationFieldOptionFactory(field=origin, title="NL", slots=2)
        cls.option_intl = RegistrationFieldOptionFactory(field=origin, title="INTL", slots=2)

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

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
        if success:
            self.assertRedirects(response, self.redirect_to)
        else:
            self.assertFormError(response, 'form', self.consent_field, self.consent_error)

        if should_exist:
            details = MedicalDetails.objects.get(user=self.user)
        else:
            with self.assertRaises(MedicalDetails.DoesNotExist):
                MedicalDetails.objects.get(user=self.user)

        # Details should be unchanged if they existed beforehand and no consent was given or withdrawn
        if self.with_existing_details and consent is None:
            self.assertDictEqual(model_to_dict(self.details), model_to_dict(details))

        if consent is None:
            self.assertEqual(ConsentLog.objects.count(), 0)
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
