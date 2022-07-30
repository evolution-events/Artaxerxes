from unittest import mock

from django.db.utils import OperationalError
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized, parameterized_class

from apps.core.models import ConsentLog
from apps.events.tests.factories import EventFactory
from apps.people.models import MedicalDetails
from apps.people.tests.factories import ArtaUserFactory, MedicalDetailsFactory

from .factories import RegistrationFactory


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
