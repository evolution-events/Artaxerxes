from django.test import TestCase

from apps.events.tests.factories import EventFactory

from ..models import Registration
from ..services import RegistrationStatusService
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestAnnotations(TestCase):
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
