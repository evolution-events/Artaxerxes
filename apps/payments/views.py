import reversion
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin

from .models import Payment
from .services import PaymentStatusService


@method_decorator(csrf_exempt, name='dispatch')
class PaymentChanged(SingleObjectMixin, View):
    model = Payment

    def post(self, request, pk):
        payment = self.get_object()
        mollie_id = self.request.POST['id']
        if payment.mollie_id != mollie_id:
            raise SuspiciousOperation("Invalid mollie id")

        with reversion.create_revision():
            PaymentStatusService.update_payment_status(payment)
            reversion.set_comment(_("Payment status changed to {} / {} from webhook ({} / {}).").format(
                payment.status.id, payment.mollie_status, payment.id, payment.mollie_id))

        return HttpResponse("OK")
