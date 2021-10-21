from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature

from apps.events.tests.factories import EventFactory
from apps.payments.tests.factories import PaymentFactory

from ..models import Registration
from ..services import RegistrationStatusService
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


class TestPriceAndPaidAnnotation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory()

        cls.field1 = RegistrationFieldFactory(event=cls.event, name="field1")
        cls.opt1a = RegistrationFieldOptionFactory(field=cls.field1, title="opt2a", price=100)
        cls.field2 = RegistrationFieldFactory(event=cls.event, name="field2")
        cls.opt2a = RegistrationFieldOptionFactory(field=cls.field2, title="opt2a", price=50)

    def test_price_and_payments(self):
        """
        Test that the price and paid amounts are correct when combined.

        This test in particular tries to verify https://code.djangoproject.com/ticket/10060 does not happen.
        """
        options = [self.opt1a, self.opt2a]
        reg = RegistrationFactory(event=self.event, options=options)
        payments = [
            PaymentFactory(registration=reg, amount=150, completed=True),
            PaymentFactory(registration=reg, amount=250, completed=True),
        ]

        reg = Registration.objects.with_price().with_paid().get(pk=reg.pk)
        self.assertEqual(reg.price, sum(o.price for o in options))
        self.assertEqual(reg.paid, sum(p.amount for p in payments))


class TestIsCurrentAnnotation(TestCase):
    def test_is_current(self):
        """ Check the is_current annotation """
        for status in Registration.statuses.constants:
            with self.subTest(status=status):
                reg = RegistrationFactory(status=status)
                reg = Registration.objects.get(pk=reg.pk)
                if status == Registration.statuses.CANCELLED:
                    self.assertEqual(reg.is_current, False)
                else:
                    self.assertEqual(reg.is_current, True)


class TestWaitinglistAboveProperty(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True, slots=0)

    def check_order_helper(self, regs):
        """ Check that the waiting list order, as implied by waiting_list_above, matches the given iterable """
        aboves = [reg.waitinglist_above for reg in regs]
        self.assertListEqual(aboves, list(range(len(aboves))))

    def test_in_order(self):
        """ Test waitinglist registrations only, made in order """
        regs = [RegistrationFactory(event=self.event, status=Registration.statuses.WAITINGLIST) for i in range(5)]
        self.check_order_helper(regs)

    def test_interleaved(self):
        """ Test waitinglist registrations interleaved with other statuses """
        ss = Registration.statuses
        # First, a bunch of non-waitinglist registrations with all possible statuses
        regs = [RegistrationFactory(event=self.event, status=s) for s in ss.constants if s != ss.WAITINGLIST]
        # Then a waitinglist registration
        wl1 = RegistrationFactory(event=self.event, status=Registration.statuses.WAITINGLIST)
        # Then, more non-waitinglist registrations
        regs.extend([RegistrationFactory(event=self.event, status=s) for s in ss.constants if s != ss.WAITINGLIST])
        # Finally one more waitinglist registration
        wl2 = RegistrationFactory(event=self.event, status=Registration.statuses.WAITINGLIST)

        self.check_order_helper([wl1, wl2])

    def test_reversed(self):
        """ Test waitinglist registrations where creation order and finalization order does not match """

        regs = [
            RegistrationFactory(event=self.event, status=Registration.statuses.PREPARATION_COMPLETE)
            for i in range(5)
        ]

        for reg in reversed(regs):
            RegistrationStatusService.finalize_registration(reg)

        self.check_order_helper(reversed(regs))


class TestAdmitImmediatelyProperty(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)
        cls.event_imm_false = EventFactory(registration_opens_in_days=-1, public=True, admit_immediately=False)

        cls.type = RegistrationFieldFactory(event=cls.event_imm_false, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew", admit_immediately=True)

    def test_event_admit_immediately_true(self):
        """ Check that by default, events admit immediately"""
        e = EventFactory(registration_opens_in_days=-1, public=True)
        reg = RegistrationFactory(event=e, status=Registration.statuses.PREPARATION_COMPLETE)
        self.assertEqual(reg.admit_immediately, True)

    def test_event_admit_immediately_false(self):
        """ Check that admit_immediately=False on an event makes admit_immediately False """
        e = EventFactory(registration_opens_in_days=-1, public=True, admit_immediately=False)
        reg = RegistrationFactory(event=e, status=Registration.statuses.PREPARATION_COMPLETE)
        self.assertEqual(reg.admit_immediately, False)

    def test_option_admit_immediately_true(self):
        """ Check that admit_immediately=True on a selected option has precedence over the event """
        e = EventFactory(registration_opens_in_days=-1, public=True, admit_immediately=False)

        typeopt = RegistrationFieldFactory(event=e, name="type")
        RegistrationFieldOptionFactory(field=typeopt, title="Player")
        crew = RegistrationFieldOptionFactory(field=typeopt, title="Crew", admit_immediately=True)

        reg = RegistrationFactory(event=e, status=Registration.statuses.PREPARATION_COMPLETE, options=[crew])
        self.assertEqual(reg.admit_immediately, True)
