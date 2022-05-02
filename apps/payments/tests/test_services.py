import datetime
import itertools

from django.test import RequestFactory, TestCase
from parameterized import parameterized

from ..models import Payment
from ..services import PaymentService, PaymentStatusService
from .factories import PaymentFactory
from .utils import MockMollieMixin

mollie_statuses = [
    ('open', Payment.statuses.PENDING),
    ('canceled', Payment.statuses.FAILED),
    ('pending', Payment.statuses.PENDING),
    ('expired', Payment.statuses.FAILED),
    ('failed', Payment.statuses.FAILED),
    ('paid', Payment.statuses.COMPLETED),
]


class TestPaymentStatusService(MockMollieMixin, TestCase):
    @parameterized.expand(itertools.product(Payment.statuses.constants))
    def test_manual_payment(self, status):
        """ Check that manual payments are rejected, regardless of status. """
        with self.assertRaisesMessage(ValueError, "mollie"):
            payment = PaymentFactory(status=status)
            PaymentStatusService.update_payment_status(payment)

    def change_status_helper(self, to_mollie_status, to_status=None, payment=None, updated_at=None):
        """ Helper that calls update_payment_status and checks the outcome. """
        if payment is None:
            payment = PaymentFactory(mollie=True)
        if updated_at is None:
            updated_at = datetime.datetime.now(datetime.timezone.utc)

        self.add_mollie_payment(payment.mollie_id, to_mollie_status, updated_at=updated_at)

        original_status = payment.status
        original_mstatus = payment.mollie_status
        original_timestamp = payment.timestamp

        try:
            PaymentStatusService.update_payment_status(payment)
            payment.refresh_from_db()

            if to_status is not None:
                self.assertEqual(payment.mollie_status, to_mollie_status)
                self.assertEqual(payment.status, to_status)
                if to_status != Payment.statuses.PENDING:
                    self.assertEqual(payment.timestamp, updated_at)
        except AssertionError:
            raise
        except Exception:
            # Assert unchanged on exception
            self.assertEqual(payment.status, original_status)
            self.assertEqual(payment.mollie_status, original_mstatus)
            self.assertEqual(payment.timestamp, original_timestamp)
            raise

        self.mollie_client.payments.get.assert_called()
        self.mollie_client.payments.create.assert_not_called()

        return payment

    @parameterized.expand(mollie_statuses)
    def test_change_status(self, mollie_status, status):
        """ Check that changing from open to any status is ok """
        self.change_status_helper(mollie_status, status)

    @parameterized.expand(
        (pending_mstatus, pending_status, next_mstatus, next_status)
        for pending_mstatus, pending_status in mollie_statuses
        for next_mstatus, next_status in mollie_statuses
        if pending_status == Payment.statuses.PENDING
    )
    def test_from_pending(self, pending_mstatus, pending_status, next_mstatus, next_status):
        """ Check that changing from any pending status to any status is ok. """
        payment = self.change_status_helper(pending_mstatus, pending_status)
        self.change_status_helper(next_mstatus, next_status, payment=payment)

    @parameterized.expand(
        (final_mstatus, final_status, next_mstatus)
        for final_mstatus, final_status in mollie_statuses
        for next_mstatus, _ in mollie_statuses
        if final_status != Payment.statuses.PENDING and final_mstatus != next_mstatus
    )
    def test_from_final(self, final_mstatus, final_status, next_mstatus):
        """ Check that changing from any final status is rejected. """
        payment = self.change_status_helper(final_mstatus, final_status)
        with self.assertRaisesMessage(ValueError, "already"):
            self.change_status_helper(next_mstatus, payment=payment)

    @parameterized.expand(
        (final_mstatus, final_status)
        for final_mstatus, final_status in mollie_statuses
        if final_status != Payment.statuses.PENDING
    )
    def test_from_final_timestamp_changed(self, final_mstatus, final_status):
        """ Check that changing the timestamp in any final status is rejected. """
        payment = self.change_status_helper(final_mstatus, final_status)
        updated_at = payment.timestamp + datetime.timedelta(seconds=1)
        with self.assertRaisesMessage(ValueError, "already"):
            self.change_status_helper(final_mstatus, payment=payment, updated_at=updated_at)

    @parameterized.expand(mollie_statuses)
    def test_update_again(self, mollie_status, status):
        """ Check that updating twice is always ok. """
        payment = self.change_status_helper(mollie_status, status)
        self.change_status_helper(mollie_status, status, payment=payment, updated_at=payment.timestamp)

    def test_invalid_status(self):
        """ Check that invalid statuss are rejected. """
        with self.assertRaisesMessage(ValueError, "Unknown"):
            self.change_status_helper("nonexisting")


class TestPaymentService(MockMollieMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        # Just any request to allow building absolute uris
        cls.request = RequestFactory().get('/')
        pass

    def test_starting_payment(self):
        """ Check starting a payment. """
        amount = 10
        payment = PaymentFactory(amount=amount, pending=True)
        registration = payment.registration
        next_url = 'foo'

        checkout_url = PaymentService.start_payment(self.request, payment, next_url)
        self.assert_single_payment_started(payment, registration, amount, next_url, checkout_url)

    @parameterized.expand(itertools.product([-1, 0]))
    def test_invalid_amount(self, amount):
        """ Check starting with an invalid amount is rejected. """
        payment = PaymentFactory(amount=amount, pending=True)
        next_url = 'foo'
        with self.assertRaisesMessage(ValueError, "amount"):
            PaymentService.start_payment(self.request, payment, next_url)

    @parameterized.expand(mollie_statuses)
    def test_already_started(self, mollie_status, status):
        """ Check starting is rejected if there is already a mollie_id, regardless of status """
        payment = PaymentFactory(status=status, mollie_id="abc", mollie_status=status)

        next_url = 'foo'
        with self.assertRaisesMessage(ValueError, "already"):
            PaymentService.start_payment(self.request, payment, next_url)
