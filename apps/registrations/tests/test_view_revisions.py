from unittest import skip

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from reversion.models import Revision

from apps.events.tests.factories import EventFactory
from apps.people.models import Address, ArtaUser, EmergencyContact, MedicalDetails
from apps.people.tests.factories import AddressFactory, ArtaUserFactory

from ..models import Registration, RegistrationFieldValue
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestRevisions(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew")

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    def assertRevision(self, revision, models, fields=None):
        """ Assert that the given is correct and returns Version objects for the given models. """
        if fields is not None:
            split = revision.get_comment().split("fields changed: ", 1)
            self.assertEqual(len(split), 2, msg="Revision comment should contain changed fields list")
            changed_fields = split[1].split(", ")
            self.assertEqual(
                sorted(changed_fields), sorted(fields),
                msg="Revision comment changed fields should match expected fields",
            )
        self.assertEqual(revision.user, self.user)

        result = []
        versions = list(revision.version_set.all())
        for model in models:
            for i, version in enumerate(versions):
                if version.content_type.model_class() == model:
                    result.append(versions.pop(i))
                    break
            else:
                self.fail("Revision should contain version for {}".format(model))
        self.assertEqual(versions, [], msg="Revision should not contain extra versions")
        return result

    def assertFields(self, version, included=(), excluded=()):
        """ Assert that the give Version contains values for the right fields. """
        for f in included:
            self.assertIn(f, version.field_dict)

        for f in excluded:
            self.assertNotIn(f, version.field_dict)

    def test_registration_start(self):
        """ Check created revisions for start step. """
        # First post should create a single revision
        url = reverse('registrations:registration_start', args=(self.event.pk,))
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertRevision(Revision.objects.get(), [Registration])

        # Post again, should not create another revision
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

    def test_registration_options(self):
        """ Check created revisions for options step. """
        reg = RegistrationFactory(event=self.event, user=self.user)
        url = reverse('registrations:step_registration_options', args=(reg.pk,))

        # First post should create a single revision
        data = {self.type.name: self.player.pk}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        self.assertRevision(revision, [Registration, RegistrationFieldValue], [self.type.name])

        # Post again with unmodified data, should not create another revision
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

        # Post again with modified data, should create another revision
        data = {self.type.name: self.crew.pk}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        second_revision = Revision.objects.exclude(pk=revision.pk).get()
        self.assertRevision(second_revision, [Registration, RegistrationFieldValue], [self.type.name])

    def test_personal_details(self):
        """ Check created revisions for personal details step. """
        reg = RegistrationFactory(event=self.event, user=self.user)
        url = reverse('registrations:step_personal_details', args=(reg.pk,))

        # First post should create a single revision
        data = {
            'user-first_name': 'foo',
            'user-last_name': 'bar',
            'address-phone_number': '+31101234567',
            'address-address': 'Some Street 123',
            'address-postalcode': '1234',
            'address-city': 'Town',
            'address-country': 'Country',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        user_fields = [field.split("-")[1] for field in data if field.split("-")[0] == "user"]
        address_fields = [field.split("-")[1] for field in data if field.split("-")[0] == "address"]
        changed_fields = user_fields + address_fields
        changed_fields = address_fields + user_fields
        user_version, address_version = self.assertRevision(revision, [ArtaUser, Address], changed_fields)
        self.assertFields(user_version, included=user_fields)
        self.assertFields(address_version, excluded=address_fields)

        # Post again with unmodified data, should not create another revision
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

        # Post again with modified user data, should create another revision
        data['user-first_name'] = 'xxx'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        second_revision = Revision.objects.exclude(pk=revision.pk).get()
        self.assertRevision(second_revision, [ArtaUser, Address], ['first_name'])

        # Post again with modified address data, should create another revision
        data['address-city'] = 'xxx'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        third_revision = Revision.objects.exclude(pk__in=[revision.pk, second_revision.pk]).get()
        self.assertRevision(third_revision, [ArtaUser, Address], ['city'])

    def test_medical_details(self):
        """ Check created revisions for medical details step. """
        reg = RegistrationFactory(event=self.event, user=self.user)
        url = reverse('registrations:step_medical_details', args=(reg.pk,))

        # First post should create a single revision
        info_fields = ['food_allergies', 'event_risks']
        data = {
            info_fields[0]: 'foo',
            info_fields[1]: 'bar',
            'consent': True,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        _, medical_version = self.assertRevision(revision, [ArtaUser, MedicalDetails], data.keys())
        self.assertFields(medical_version, excluded=info_fields)

        # Post again with unmodified data, should not create another revision
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Revision.objects.count(), 1, msg="Should not create new revision")

        # Post again with modified data, should create another revision
        for f in info_fields:
            data[f] += 'modified'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        second_revision = Revision.objects.exclude(pk=revision.pk).get()
        _, medical_version = self.assertRevision(second_revision, [ArtaUser, MedicalDetails], info_fields)
        self.assertFields(medical_version, excluded=info_fields)

        # Post again with empty form, should create revision without MedicalDetails present
        data = {field: '' for field in data}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        third_revision = Revision.objects.exclude(pk__in=[revision.pk, second_revision.pk]).get()
        self.assertRevision(third_revision, [ArtaUser], data.keys())

    def test_emergency_contacts(self):
        """ Check created revisions for emergency contacts step. """
        # Create complete registration, to allow changing to PREPARATION_COMPLETED
        reg = RegistrationFactory(event=self.event, user=self.user, options=[self.player])
        AddressFactory(user=reg.user)
        # MedicalDetails is optional, so no need to create it

        url = reverse('registrations:step_emergency_contacts', args=(reg.pk,))

        # First post should create a one revision for the contacts and one for the registration
        info_fields = ['contact_name', 'relation', 'phone_number', 'remarks']
        data = {
            'emergency_contacts-TOTAL_FORMS': 2,
            'emergency_contacts-INITIAL_FORMS': 0,
            'emergency_contacts-0-contact_name': 'First name',
            'emergency_contacts-0-relation': 'First relation',
            'emergency_contacts-0-phone_number': '+31101234567',
            'emergency_contacts-0-remarks': 'First remarks',
            'emergency_contacts-1-contact_name': 'Second name',
            'emergency_contacts-1-relation': '',
            'emergency_contacts-1-phone_number': '+31107654321',
            'emergency_contacts-1-remarks': '',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        # First check the user/emergencycontacts revision
        emergency_contact_type = ContentType.objects.get_for_model(EmergencyContact)
        first_revision = Revision.objects.filter(version__content_type=emergency_contact_type).distinct().get()
        models = [ArtaUser, Address, EmergencyContact, EmergencyContact]
        _, _, *contact_versions = self.assertRevision(first_revision, models)
        for version in contact_versions:
            self.assertFields(version, excluded=info_fields)

        # Then check the registration revision
        registration_type = ContentType.objects.get_for_model(Registration)
        second_revision = Revision.objects.filter(version__content_type=registration_type).get()
        registration_version, _ = self.assertRevision(second_revision, [Registration, RegistrationFieldValue])
        self.assertFields(registration_version, included=['status'])

        # TODO: Check unmodified repost, which is a bit complicated since it requires adding emergency contact ids to
        # the form. Maybe a GET and submit that form would be easier?

    @skip("revision creation disabled for speed")
    def test_final_check(self):
        """ Check created revisions for final check step. """
        reg = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)

        url = reverse('registrations:step_final_check', args=(reg.pk,))

        # Post should create a one revision
        data = {'agree': True}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        (version,) = self.assertRevision(revision, [Registration])
        self.assertFields(version, included=['status'])
