from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature

from .factories import RegistrationFactory


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
