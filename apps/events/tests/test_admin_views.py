from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.people.tests.factories import ArtaUserFactory
from apps.registrations.tests.factories import RegistrationFieldFactory, RegistrationFieldOptionFactory

from .factories import EventFactory


class TestCopyFieldsView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.copy_from = EventFactory()
        cls.copy_to = EventFactory()

        cls.staff_with_permission = ArtaUserFactory(is_staff=True, permissions=['events.change_event'])
        cls.staff_without_permission = ArtaUserFactory(is_staff=True)
        cls.nonstaff = ArtaUserFactory()

        cls.type = RegistrationFieldFactory(event=cls.copy_from, name="type")
        cls.type_1 = RegistrationFieldOptionFactory(field=cls.type, title="Type 1")
        cls.type_2 = RegistrationFieldOptionFactory(field=cls.type, title="Type 2")

        cls.field_with_depends = RegistrationFieldFactory(
            event=cls.copy_from, name="field_with_depends", depends=cls.type_1)
        cls.field_with_depends_1 = RegistrationFieldOptionFactory(
            field=cls.field_with_depends, title="Field with depends 1")
        cls.field_with_depends_2 = RegistrationFieldOptionFactory(
            field=cls.field_with_depends, title="Field with depends 2")

        cls.field_opt_depends = RegistrationFieldFactory(
            event=cls.copy_from, name="field_opt_depends")
        cls.field_opt_depends_1 = RegistrationFieldOptionFactory(
            field=cls.field_opt_depends, title="Field with options with depends 1",
            depends=cls.type_2)

        cls.duplicate = RegistrationFieldFactory(event=cls.copy_from, name="duplicate")
        cls.duplicate_1 = RegistrationFieldOptionFactory(field=cls.duplicate, title="Duplicate 1")
        RegistrationFieldFactory(event=cls.copy_to, name="duplicate")

    def setUp(self):
        self.client.force_login(self.staff_with_permission)

    def test_copy_type(self):
        """ Check that copying a single field only copies that field. """
        self.copy_helper(fields=[self.type], expected_fields={'duplicate': set(), 'type': {'Type 1', 'Type 2'}})

    def test_copy_all(self):
        """ Check that copying all non-duplicate fields works and copies depends as well. """
        self.copy_helper(
            fields=[self.type, self.field_with_depends, self.field_opt_depends],
            expected_fields={
                'duplicate': set(),
                'type': {'Type 1', 'Type 2'},
                'field_with_depends': {'Field with depends 1', 'Field with depends 2'},
                'field_opt_depends': {'Field with options with depends 1'},
            },
            expected_depends={
                'field_with_depends': 'Type 1',
                'Field with options with depends 1': 'Type 2',
            },
        )

    def test_copy_missing_depends(self):
        """ Check that not copying a depended-on option is shown to the user. """
        self.copy_helper(
            fields=[self.field_with_depends, self.field_opt_depends],
            expected_fields={
                'duplicate': set(),
                'field_with_depends': {'Field with depends 1', 'Field with depends 2'},
                'field_opt_depends': {'Field with options with depends 1'},
            },
            expected_depends={},
            dropped_depends={
                'field_with_depends': 'Type 1',
                'Field with options with depends 1': 'Type 2',
            },
        )

    def test_copy_duplicate(self):
        """ Check that copying the duplicate field fails and copies nothing. """

        with self.assertRaises(IntegrityError):
            self.copy_helper(
                fields=[self.type, self.duplicate],
                expected_fields={'duplicate': set()},
            )

    def test_copy_no_permission(self):
        """ Copy without permissions redirects to login page """
        self.client.force_login(self.staff_without_permission)
        # This should redirect to the login page, but because of the next_url parameter and another redirect this is a
        # bit tricky to assert, so just check that it redirects somewhere.
        self.copy_helper(
            fields=[self.type],
            expected_fields={'duplicate': set()},
            status_code=302,
        )

    def test_copy_no_staff(self):
        """ Copy for non-staff redirects to login page """
        self.client.force_login(self.nonstaff)
        # This should redirect to the login page, but because of the next_url parameter and another redirect this is a
        # bit tricky to assert, so just check that it redirects somewhere.
        self.copy_helper(
            fields=[self.type],
            expected_fields={'duplicate': set()},
            status_code=302,
        )

    def copy_helper(self, *, fields, expected_fields, expected_depends=None, dropped_depends=None, status_code=200):
        """ Helper to call copy view and check result. """
        url = reverse('admin:copy_event_fields', args=(self.copy_to.pk,))

        try:
            response = self.client.post(url, {
                'copy_from': self.copy_from.pk,
                'fields': [field.pk for field in fields],
            })
        except Exception:
            raise
        else:
            self.assertEqual(response.status_code, status_code)

            if status_code == 200:
                self.assertTemplateUsed(response, 'events/admin/copy_fields_complete.html')

                actual_dropped_depends = {
                    getattr(obj, 'name', None) or obj.title: depends.title
                    for obj, depends in response.context['dropped_depends'].items()
                }
                self.assertEqual(actual_dropped_depends, dropped_depends or {})
        finally:
            actual_fields = {
                field.name: {option.title for option in field.options.all()}
                for field in self.copy_to.registration_fields.all()
            }

            self.assertEqual(actual_fields, expected_fields)

            actual_depends = {
                field.name: field.depends
                for field in self.copy_to.registration_fields.all()
                if field.depends
            }
            actual_depends.update({
                option.title: option.depends
                for field in self.copy_to.registration_fields.all()
                for option in field.options.all()
                if option.depends
            })

            for _, depends in actual_depends.items():
                self.assertEqual(depends.field.event, self.copy_to)

            actual_depends = {objname: depends.title for objname, depends in actual_depends.items()}

            self.assertEqual(actual_depends, expected_depends or {})

        return response
