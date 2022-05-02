import itertools

from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature
from parameterized import parameterized

from apps.events.tests.factories import EventFactory
from apps.payments.models import Payment
from apps.payments.tests.factories import PaymentFactory

from ..models import Registration
from ..services import RegistrationStatusService
from .factories import (RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory,
                        RegistrationPriceCorrectionFactory)


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


class TestPaymentAnnotations(TestCase):
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

        cls.s = Registration.statuses
        cls.ps = Registration.payment_statuses

    def check_helper(self, options, price, amount_due, payments=(), corrections=(), cancelled_corrections=(),
                     paid=None, payment_status=Registration.payment_statuses.OPEN,
                     status=Registration.statuses.REGISTERED):
        """ Create a registration, payments and check the resulting annotations. """
        reg = RegistrationFactory(event=self.event, options=options, status=status)

        def create(info):
            if isinstance(info, tuple):
                (amount, status) = info
            else:
                amount = info
                status = Payment.statuses.COMPLETED

            return PaymentFactory(registration=reg, amount=amount, status=status)

        for p in payments:
            create(p)
        for p in corrections:
            RegistrationPriceCorrectionFactory(registration=reg, price=p, when_cancelled=False)
        for p in cancelled_corrections:
            RegistrationPriceCorrectionFactory(registration=reg, price=p, when_cancelled=True)

        reg = Registration.objects.with_payment_status().get(pk=reg.pk)
        self.assertEqual(reg.price, price)
        self.assertEqual(reg.paid, paid)
        self.assertEqual(reg.amount_due, amount_due)
        self.assertEqual(reg.payment_status, payment_status)

    def test_no_priced_options(self):
        """ Test that no priced options produces None price """
        self.check_helper(
            options=[self.free],
            price=None,
            amount_due=0,
            payment_status=self.ps.FREE,
        )

    def test_single_priced_option(self):
        """ Test a registration with a single priced option """
        self.check_helper(
            options=[self.crew],
            price=50,
            amount_due=50,
        )

    def test_sum_priced_options(self):
        """ Test that multiple priced options are summed """
        self.check_helper(
            options=[self.player, self.donation_yes],
            price=175,
            amount_due=175,
        )

    def test_negative_priced_option(self):
        """ Test that negative priced options are subtracted """
        self.check_helper(
            options=[self.player, self.discount_yes],
            price=90,
            amount_due=90,
        )

    def test_only_correction(self):
        """ Test a registration with a single correction """
        self.check_helper(
            options=[self.free],
            corrections=[10],
            price=10,
            amount_due=10,
        )

    def test_multiple_corrections(self):
        """ Test a registration with multiple corrections """
        self.check_helper(
            options=[self.free],
            corrections=[10, 20],
            price=30,
            amount_due=30,
        )

    def test_option_and_multiple_corrections(self):
        """ Test a registration with an option and multiple corrections """
        self.check_helper(
            options=[self.player],
            corrections=[10, 20],
            price=130,
            amount_due=130,
        )

    def test_unused_cancelled_corrections(self):
        """ Test that cancelled corrections are not used when the registration is not cancelled """
        self.check_helper(
            options=[self.player],
            cancelled_corrections=[10],
            price=100,
            amount_due=100,
        )

    @parameterized.expand(itertools.product([
        Registration.statuses.PREPARATION_IN_PROGRESS,
        Registration.statuses.PREPARATION_COMPLETE,
        Registration.statuses.WAITINGLIST,
        Registration.statuses.PENDING,
    ]))
    def test_non_admitted(self, status):
        """ Test that non-admitted registrations are not due. """
        self.check_helper([self.player], price=100, status=status, amount_due=None, payment_status=self.ps.NOT_DUE)

    @parameterized.expand(itertools.product([
        Registration.statuses.PREPARATION_IN_PROGRESS,
        Registration.statuses.PREPARATION_COMPLETE,
        Registration.statuses.WAITINGLIST,
        Registration.statuses.PENDING,
    ]))
    def test_free_non_admitted(self, status):
        """ Test that free non-admitted registrations are free. """
        self.check_helper([self.free], price=None, status=status, amount_due=None, payment_status=self.ps.FREE)

    def test_paid(self):
        """ Test that registrations with full payments are paid. """
        self.check_helper(
            options=[self.player],
            payments=[100],
            price=100,
            paid=100,
            amount_due=0,
            payment_status=self.ps.PAID,
        )

    def test_paid_multiple(self):
        """ Test that registrations with multiple pricing and payments. """
        self.check_helper(
            options=[self.player, self.donation_yes],
            payments=[100, 75],
            price=175,
            paid=175,
            amount_due=0,
            payment_status=self.ps.PAID,
        )

    def test_free_refunded(self):
        """ Test that free registrations with refunds are REFUNDED. """
        # These can occur when a payment has been made, then all paid options are removed/changed and then it is
        # refunded.
        self.check_helper(
            options=[self.free],
            payments=[100, -100],
            price=None,
            paid=0,
            amount_due=0,
            payment_status=self.ps.REFUNDED,
        )

    def test_cancelled(self):
        """ Test that cancelled registrations have a zero price. """
        self.check_helper(
            options=[self.player],
            corrections=[10],
            status=self.s.CANCELLED,
            price=0,
            amount_due=0,
            payment_status=self.ps.FREE,
        )

    def test_cancelled_free(self):
        """ Test that cancelled registrations without paid options are FREE. """
        self.check_helper(
            options=[self.free],
            status=self.s.CANCELLED,
            price=0,
            amount_due=0,
            payment_status=self.ps.FREE,
        )

    def test_cancelled_corrections(self):
        """ Test that cancelled corrections are applied for cancelled registrations. """
        self.check_helper(
            options=[self.player],
            corrections=[10],
            cancelled_corrections=[20],
            status=self.s.CANCELLED,
            price=20,
            amount_due=20,
            payment_status=self.ps.OPEN,
        )

    def test_paid_cancelled_corrections(self):
        """ Test that payment of a cancelled correction is correctly registered. """
        self.check_helper(
            options=[self.player],
            corrections=[10],
            cancelled_corrections=[20],
            payments=[20],
            status=self.s.CANCELLED,
            price=20,
            paid=20,
            amount_due=0,
            payment_status=self.ps.PAID,
        )

    def test_free_cancelled_refunded(self):
        """ Test that free cancelled registrations with refunds are REFUNDED. """
        # These can occur when a payment has been made, then all paid options are removed and then it is cancelled and
        # refunded.
        self.check_helper(
            options=[self.free],
            status=self.s.CANCELLED,
            payments=[100, -100],
            paid=0,
            price=0,
            amount_due=0,
            payment_status=self.ps.REFUNDED,
        )

    def test_cancelled_with_payments(self):
        """ Test that cancelled registrations with full payments are refundable. """
        self.check_helper(
            options=[self.player],
            payments=[100],
            status=self.s.CANCELLED,
            paid=100,
            price=0,
            amount_due=-100,
            payment_status=self.ps.REFUNDABLE,
        )

    def test_cancelled_with_refunds(self):
        """ Test that cancelled registrations with payment and refunds are refunded. """
        self.check_helper(
            options=[self.player],
            payments=[100, -100],
            status=self.s.CANCELLED,
            price=0,
            paid=0,
            amount_due=0,
            payment_status=self.ps.REFUNDED,
        )

    def test_cancelled_multiple(self):
        """ Test that cancelled registrations with multiple prices, payments and refunds. """
        self.check_helper(
            options=[self.player, self.donation_yes],
            payments=[100, 75, -50, -125],
            status=self.s.CANCELLED,
            price=0,
            paid=0,
            amount_due=0,
            payment_status=self.ps.REFUNDED,
        )

    def test_cancelled_with_partial_refunds(self):
        """ Test that cancelled registrations with partial refunds are refundable. """
        self.check_helper(
            options=[self.player],
            payments=[100, -50],
            status=self.s.CANCELLED,
            price=0,
            paid=50,
            amount_due=-50,
            payment_status=self.ps.REFUNDABLE,
        )

    def test_cancelled_over_refunded(self):
        """ Test that cancelled registrations with too much refunds still need to be paid. """
        self.check_helper(
            options=[self.player],
            payments=[100, -150],
            status=self.s.CANCELLED,
            price=0,
            paid=-50,
            amount_due=50,
            payment_status=self.ps.PARTIAL,
        )

    def test_cancelled_corrections_refunded(self):
        """ Test a cancelled registrations with a cancelled correction and payment and matching refund. """
        self.check_helper(
            options=[self.player],
            payments=[110, -90],
            corrections=[10],
            cancelled_corrections=[20],
            status=self.s.CANCELLED,
            price=20,
            paid=20,
            amount_due=0,
            payment_status=self.ps.PAID,
        )

    def test_partial(self):
        """ Test that partial payments are correctly registered. """
        self.check_helper(
            options=[self.player],
            payments=[25],
            payment_status=self.ps.PARTIAL,
            paid=25,
            price=100,
            amount_due=75,
        )

    def test_partially_refunded_but_still_due(self):
        """ Test that partially paid registrations including refunds are PARTIAL. """
        # These can occur when a payment has been made, then options are removed and refunded, and then options are
        # added again. Or when a refund is made without also updating the registration options.
        self.check_helper(
            options=[self.player],
            payments=[100, -50],
            price=100,
            paid=50,
            amount_due=50,
            payment_status=self.ps.PARTIAL,
        )

    def test_fully_refunded_but_still_due(self):
        """ Test that fully refunded but still due registrations are OPEN. """
        # This can occur when a refund is made without also cancelling/updating the registration.
        self.check_helper(
            options=[self.player],
            payments=[100, -100],
            price=100,
            paid=0,
            amount_due=100,
            payment_status=self.ps.OPEN,
        )

    def test_multiple_price_and_payments(self):
        """
        Test that the price and paid amounts are correct when combined.

        This test in particular tries to verify https://code.djangoproject.com/ticket/10060 does not happen.
        """
        self.check_helper(
            options=[self.player, self.donation_yes],
            payments=[75, 25],
            payment_status=self.ps.PARTIAL,
            paid=100,
            price=175,
            amount_due=75,
        )


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
