import datetime

from django.conf import settings
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from mollie.api.client import Client

from .models import Payment

# This takes some extra care to not accidentally use a live API key, even when running unittests on a live checkout.
# In testcases, this code can still be ran by mocking mollie_client (or patching it with an actual instance for
# integration testing if needed).
if getattr(settings, 'IN_UNITTEST', False):
    mollie_client = None
else:
    # TODO: Allow development without an API key too? Maybe allow failing if DEBUG?
    mollie_client = Client()
    mollie_client.set_api_key(settings.MOLLIE_API_KEY)


class PaymentStatusService:
    @staticmethod
    def update_payment_status(payment):
        """ Retrieves the remote status of the given payment and update the local status. """

        if not payment.mollie_id:
            raise ValueError("Not a mollie payment?")

        mp = mollie_client.payments.get(payment.mollie_id)

        if mp.is_paid():
            newstatus = Payment.statuses.COMPLETED
            timestamp = mp.paid_at
        elif mp.is_expired():
            newstatus = Payment.statuses.FAILED
            timestamp = mp.expired_at
        elif mp.is_failed():
            newstatus = Payment.statuses.FAILED
            timestamp = mp.failed_at
        elif mp.is_canceled():
            newstatus = Payment.statuses.FAILED
            timestamp = mp.canceled_at
        elif mp.is_authorized():
            raise ValueError("Authorized state not implemented")
        elif mp.is_open() or mp.is_pending():
            newstatus = Payment.statuses.PENDING
            timestamp = None
        else:
            raise ValueError("Unknown state")

        if timestamp is not None:
            timestamp = datetime.datetime.fromisoformat(timestamp)

        if payment.status.PENDING:
            if newstatus != Payment.statuses.PENDING:
                payment.status = newstatus
                payment.timestamp = timestamp
        else:
            if payment.status != newstatus:
                raise ValueError("Payment status changed when already final?")
            if payment.timestamp != timestamp:
                raise ValueError("Payment timestamp changed when already final?")

        payment.mollie_status = mp.status
        payment.save()

        # TODO: Once we implement refunds, refunds for the given transaction should also be updated (they share the
        # webhook with their original payment).


class PaymentService:
    @staticmethod
    def start_payment(request, payment, next_url, method=''):
        """ Create a new payment, returning the payment object and the url to send the user to to pay. """

        if payment.amount <= 0:
            raise ValueError("Invalid amount: {}".format(payment.amount))

        if payment.mollie_id:
            raise ValueError("Payment already started")

        registration = payment.registration

        # TODO: If this is a partial or additional payment, modify message?
        message = _("{event} / {name} / {num}").format(
            num=registration.id, event=registration.event.name, name=registration.user.full_name)

        mp = mollie_client.payments.create({
            "amount": {"currency": "EUR", "value": format(payment.amount, '.2f')},
            "description": message,
            "webhookUrl": request.build_absolute_uri(reverse('payments:webhook', args=(payment.pk,))),
            "redirectUrl": request.build_absolute_uri(next_url),
            "method": method,
            "metadata": {
                "payment_id": str(payment.pk),
                "registration_id": str(registration.pk),
            },
        })

        payment.mollie_id = mp.id
        payment.mollie_status = mp.status
        payment.save()

        return mp.checkout_url
