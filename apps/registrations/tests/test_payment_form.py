import itertools

from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from with_asserts.mixin import AssertHTMLMixin

from apps.events.tests.factories import EventFactory
from apps.payments.models import Payment
from apps.payments.tests.utils import MockMollieMixin
from apps.people.tests.factories import ArtaUserFactory
from apps.registrations.models import Registration

from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestPayment(MockMollieMixin, AssertHTMLMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player", price=10)

    def setUp(self):
        super().setUp()
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    @parameterized.expand(itertools.product(
        [False, True],
        [
            ('canceled', Payment.statuses.FAILED),
            ('expired', Payment.statuses.FAILED),
            ('failed', Payment.statuses.FAILED),
            ('paid', Payment.statuses.COMPLETED),
        ],
    ))
    def test_full_payment(self, call_webhook, final_status):
        """ Run through an entire payment flow. """
        final_mollie_status, final_payment_status = final_status

        reg = RegistrationFactory(event=self.event, options=[self.player], user=self.user, registered=True)

        # Check the payment status is open
        status_url = reverse('registrations:payment_status', args=(reg.event.pk,))
        with self.assertTemplateUsed('registrations/payment_status.html'):
            response = self.client.get(status_url)

        self.assertContains(response, "needs payment")

        # Start the payment
        response = self.client.post(status_url, {'method': 'method_ideal'})
        checkout_url = response.url
        payment = Payment.objects.get()
        next_url = reverse('registrations:payment_done', args=(payment.pk,))

        self.assert_single_payment_started(payment, reg, self.player.price, next_url, checkout_url)

        # Simulate mollie redirecting back to payment done (but a bit early, before payment status was updated)
        with self.assertTemplateUsed('registrations/payment_done.html'):
            response = self.client.get(next_url)

        self.assertContains(response, "still pending")
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.statuses.PENDING)

        # Update status of mollie payment, simulating the payment was handled at mollie
        self.set_mollie_status(payment.mollie_id, final_mollie_status)

        # Optionally simulate mollie calling the webhook before redirecting
        if call_webhook:
            webhook_url = reverse('payments:webhook', args=(payment.pk,))
            response = self.client.post(webhook_url, {'id': payment.mollie_id})
            self.assertEqual(response.status_code, 200)

            payment.refresh_from_db()
            self.assertEqual(payment.status, final_payment_status)

            # Check payment status page was updated
            with self.assertTemplateUsed('registrations/payment_status.html'):
                response = self.client.get(status_url)
            if payment.status.COMPLETED:
                self.assertContains(response, "completely paid")
            else:
                self.assertContains(response, "needs payment")

        # Simulate mollie redirecting back to payment done (or user refreshing)
        with self.assertTemplateUsed('registrations/payment_done.html'):
            response = self.client.get(next_url)

        payment.refresh_from_db()
        self.assertEqual(payment.status, final_payment_status)

        if payment.status.COMPLETED:
            self.assertContains(response, "fully completed")
        else:
            self.assertContains(response, "failed")

        # Check payment status again
        with self.assertTemplateUsed('registrations/payment_status.html'):
            response = self.client.get(status_url)

        if payment.status.COMPLETED:
            self.assertContains(response, "completely paid")
        else:
            self.assertContains(response, "needs payment")

    @parameterized.expand(itertools.product(
        Registration.statuses.DRAFT,
    ))
    def test_not_finalized(self, status):
        """ Check that only finalized registrations can be paid """
        reg = RegistrationFactory(event=self.event, options=[self.player], user=self.user, status=status)

        start_url = reverse('registrations:registration_start', args=(reg.event.pk,))
        status_url = reverse('registrations:payment_status', args=(reg.event.pk,))
        response = self.client.get(status_url, follow=False)
        self.assertRedirects(response, start_url, target_status_code=302)

        response = self.client.post(status_url, {'method': 'ideal'}, follow=False)
        self.assertRedirects(response, start_url, target_status_code=302)
