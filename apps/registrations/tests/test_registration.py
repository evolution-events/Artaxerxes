from django.conf import settings
from django.core import mail
from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature
from django.urls import reverse

from apps.events.tests.factories import EventFactory
from apps.people.tests.factories import ArtaUserFactory

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
        check_url = reverse('registrations:finalcheckform', args=(reg.pk,))
        confirm_url = reverse('registrations:registrationconfirmation', args=(reg.pk,))
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
        check_url = reverse('registrations:finalcheckform', args=(reg.pk,))
        confirm_url = reverse('registrations:registrationconfirmation', args=(reg.pk,))
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
        start_url = reverse('registrations:register', args=(e.pk,))
        with self.assertTemplateUsed('registrations/registration_start.html'):
            self.client.get(start_url)

        # Send a post request to start registration procedure, this should created a new Registration and redirect to
        # the next step.
        response = self.client.post(start_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        reg = Registration.objects.get(user=self.user, event=e)
        first_step_url = reverse('registrations:optionsform', args=(reg.pk,))
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
        final_check_url = reverse('registrations:finalcheckform', args=(reg.pk,))
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
