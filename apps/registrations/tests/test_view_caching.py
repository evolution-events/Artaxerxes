import time
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from unittest import mock, skip

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.tests.factories import EventFactory
from apps.people.tests.factories import AddressFactory, ArtaUserFactory, EmergencyContactFactory, MedicalDetailsFactory

from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestCaching(TestCase):
    def setUp(self):
        self.event = EventFactory(starts_in_days=2, registration_opens_in_days=-1, public=True)

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
