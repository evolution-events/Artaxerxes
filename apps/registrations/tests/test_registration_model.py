from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature

from apps.events.tests.factories import EventFactory

from ..models import Registration
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


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


class TestPriceAnnotation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory()

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player", price=100)
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew", price=50)
        cls.free = RegistrationFieldOptionFactory(field=cls.type, title="Free")

        cls.donation = RegistrationFieldFactory(event=cls.event, name="donation", depends=cls.player)
        cls.donation_yes = RegistrationFieldOptionFactory(field=cls.donation, title="Yes", price=75)
        cls.donation_no = RegistrationFieldOptionFactory(field=cls.donation, title="No")

        cls.discount = RegistrationFieldFactory(event=cls.event, name="discount", depends=cls.player)
        cls.discount_yes = RegistrationFieldOptionFactory(field=cls.discount, title="Yes", price=-10)
        cls.discount_no = RegistrationFieldOptionFactory(field=cls.discount, title="No")

    def price_helper(self, price, options):
        reg = RegistrationFactory(event=self.event, options=options)
        reg = Registration.objects.with_price().get(pk=reg.pk)
        self.assertEqual(reg.price, price)

    def test_no_priced_options(self):
        """ Test that no priced options produces None """
        self.price_helper(None, [self.free])

    def test_single_priced_option(self):
        """ Test a registration with a single priced option """
        self.price_helper(50, [self.crew])

    def test_sum_priced_options(self):
        """ Test that multiple priced options are summed """
        self.price_helper(175, [self.player, self.donation_yes])

    def test_negative_priced_option(self):
        """ Test that negative priced options are subtracted """
        self.price_helper(90, [self.player, self.discount_yes])
