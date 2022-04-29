import datetime

import factory
from django.utils import timezone
from faker import Faker

from apps.registrations.tests.factories import RegistrationFactory

from ..models import Payment


# TODO: This is a bit of an ugly thing. The goal is to allow both using this externally (e.g. from MockMollieMixin) in
# with a new Faker instance (so new uniqueness) on every testcase, but also using it in the PaymentFactory below. Maybe
# when FactoryBoy supports uniqueness, this becomes easier?
class MollieIdFaker:
    def __init__(self):
        self.faker = Faker()
        self.factory = factory.LazyFunction(self.generate)

    def generate(self):
        return self.faker.unique.lexify(
            text='tr_??????????',
            letters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890',
        )


id_faker = MollieIdFaker()


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    amount = 10
    status = Payment.statuses.PENDING
    registration = factory.SubFactory(RegistrationFactory)
    timestamp = factory.LazyFunction(timezone.now)

    class Params:
        # These are just to more concisely define status
        pending = factory.Trait(status=Payment.statuses.PENDING)
        completed = factory.Trait(status=Payment.statuses.COMPLETED)
        failed = factory.Trait(status=Payment.statuses.FAILED)

        mollie = factory.Trait(mollie_id=id_faker.factory, mollie_status='open')
