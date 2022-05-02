import datetime
from unittest import mock

from django.core.validators import URLValidator
from django.test import RequestFactory
from django.urls import reverse
from mollie.api.objects.payment import Payment as MolliePayment

from ..models import Payment
from .factories import MollieIdFaker


class MockMollieMixin:
    def setUp(self):
        super().setUp()

        # Create a fresh patch and "database" for each testcase, so things like assert_called work as expected.
        patcher = mock.patch('apps.payments.services.mollie_client')
        self.mollie_client = patcher.start()
        self.addCleanup(patcher.stop)
        self.mollie_id_faker = MollieIdFaker()

        self.mollie_client.payments.get.side_effect = self.mollie_get
        self.mollie_client.payments.create.side_effect = self.mollie_create
        self.mollie_payments = {}

    def mollie_get(self, mollie_id):
        return self.mollie_payments[mollie_id]

    def mollie_create(self, data):
        self.assertRegex(data['amount']['value'], r'\d+.\d\d')
        self.assertEqual(data['amount']['currency'], 'EUR')
        self.assertIn('redirectUrl', data)
        self.assertIn('webhookUrl', data)

        mollie_id = self.mollie_id_faker.generate()
        return self.add_mollie_payment(mollie_id, status='open', **data)

    def add_mollie_payment(self, mollie_id, status, updated_at=None, **kwargs):
        """ Helper for testcase to add a mollie payment object, to be returned by get """
        if updated_at is None:
            updated_at = datetime.datetime.now(datetime.timezone.utc)

        # TODO: More realistic created at? Probably not used, though.
        created_at = updated_at

        # This probably does not actually include the id in practice, but any valid url probably suffices
        checkout = 'https://mollie.com/somewhere/{}'.format(mollie_id)

        mollie_payment = MolliePayment({
            'id': mollie_id,
            'status': status,
            '{}At'.format(status): updated_at.isoformat(),
            'createdAt': created_at.isoformat(),
            '_links': {
                'checkout': {'href': checkout},
            },
            **kwargs,
        })

        self.mollie_payments[mollie_id] = mollie_payment
        return mollie_payment

    def assert_single_payment_started(self, payment, registration, amount, next_url, checkout_url):
        self.assertTrue(self.mollie_client.payments.create.called_once())

        # Just a dummy request to allow building absolute uris
        request = RequestFactory().get('/')

        (mollie_payment,) = self.mollie_payments.values()
        webhook_url = reverse('payments:webhook', args=(payment.pk,))
        self.assertIn(str(registration.pk), mollie_payment.description)
        self.assertIn(registration.event.name, mollie_payment.description)
        self.assertIn(registration.user.full_name, mollie_payment.description)
        self.assertEqual(float(mollie_payment.amount['value']), amount)
        self.assertEqual(mollie_payment.redirect_url, request.build_absolute_uri(next_url))
        self.assertEqual(mollie_payment.webhook_url, request.build_absolute_uri(webhook_url))
        self.assertEqual(mollie_payment.checkout_url, checkout_url)

        self.assertNotIn(checkout_url, [None, ""])
        validate_url = URLValidator(schemes=('http', 'https'))
        validate_url(checkout_url)
        self.assertEqual(payment.amount, amount)
        self.assertEqual(payment.status, Payment.statuses.PENDING)
        self.assertEqual(payment.mollie_id, mollie_payment.id)
        self.assertEqual(payment.mollie_status, mollie_payment.status)
