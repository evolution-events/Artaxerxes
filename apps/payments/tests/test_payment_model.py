from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature
from parameterized import parameterized

from .factories import PaymentFactory


class TestConstraints(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    @parameterized.expand([
        (None, '', True),
        ('x', '', False),
        (None, 'y', False),
        ('x', 'y', True),
        # Also check empty string mollie_id is always disallowed
        ('', '', False),
        ('', 'y', False),
    ])
    @skipUnlessDBFeature('supports_table_check_constraints')
    def test_mollie_id_and_status_set_or_unset_together(self, mollie_id, mollie_status, ok):
        """ Check that mollie_id and mollie_status must always be set or unset together. """
        def create():
            PaymentFactory(mollie_id=mollie_id, mollie_status=mollie_status)
        if ok:
            create()
        else:
            self.assertRaises(IntegrityError, create)
