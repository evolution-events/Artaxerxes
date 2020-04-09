from django.db.utils import IntegrityError
from django.test import TestCase, skipUnlessDBFeature
from parameterized import parameterized

from .factories import MedicalDetailsFactory


class TestConstraints(TestCase):
    info_fields = ('food_allergies', 'event_risks')

    @skipUnlessDBFeature('supports_table_check_constraints')
    def test_empty_details(self):
        fields = {field: '' for field in self.info_fields}

        with self.assertRaises(IntegrityError):
            MedicalDetailsFactory(**fields)

    @parameterized.expand(info_fields)
    def test_non_empty_details(self, non_empty_field):
        fields = {field: '' for field in self.info_fields}
        fields[non_empty_field] = 'xxx'

        MedicalDetailsFactory(**fields)
