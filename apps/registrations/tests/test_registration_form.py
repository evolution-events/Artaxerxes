import io
import itertools
import re
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from unittest import mock, skip

from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext as _
from parameterized import parameterized
from with_asserts.mixin import AssertHTMLMixin

from apps.events.tests.factories import EventFactory
from apps.people.models import Address, EmergencyContact, MedicalDetails
from apps.people.tests.factories import ArtaUserFactory

from ..models import Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue
from ..services import RegistrationStatusService
from ..views import FinalCheck
from .factories import (RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory,
                        RegistrationFieldValueFactory)


class TestRegistrationForm(TestCase, AssertHTMLMixin):
    common_steps = (
        'registrations:step_registration_options',
        'registrations:step_personal_details',
        'registrations:step_medical_details',
        'registrations:step_emergency_contacts',
    )
    registration_steps_except_start = common_steps + (
        'registrations:step_final_check',
    )

    registration_steps = registration_steps_except_start + (
        'registrations:registration_start',
    )
    edit_steps = common_steps + (
        'registrations:edit_start',
        'registrations:edit_done',
    )
    all_steps_except_start = set(registration_steps_except_start + edit_steps)
    all_steps = all_steps_except_start | {'registrations:registration_start'}

    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True, allow_change_days=1)

        cls.type = RegistrationFieldFactory(event=cls.event, name="type", allow_change_days=1)
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.npc = RegistrationFieldOptionFactory(field=cls.type, title="NPC")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew")

        cls.gender = RegistrationFieldFactory(event=cls.event, name="gender", allow_change_days=1)
        cls.option_m = RegistrationFieldOptionFactory(field=cls.gender, title="M", slots=2)
        cls.option_f = RegistrationFieldOptionFactory(field=cls.gender, title="F", slots=2)

        cls.origin = RegistrationFieldFactory(event=cls.event, name="origin", allow_change_days=1)
        cls.option_nl = RegistrationFieldOptionFactory(field=cls.origin, title="NL", slots=2)
        cls.option_intl = RegistrationFieldOptionFactory(field=cls.origin, title="INTL", slots=2)

        cls.optional_choice = RegistrationFieldFactory(
            event=cls.event, name="optional_choice", field_type=RegistrationField.types.CHOICE, required=False,
            allow_change_days=1,
        )
        cls.optional_choice_option = RegistrationFieldOptionFactory(field=cls.optional_choice, title="oco")
        cls.optional_choice_option2 = RegistrationFieldOptionFactory(field=cls.optional_choice, title="oco2")
        cls.required_choice = RegistrationFieldFactory(
            event=cls.event, name="required_choice", field_type=RegistrationField.types.CHOICE,
            allow_change_days=1,
        )
        cls.required_choice_option = RegistrationFieldOptionFactory(field=cls.required_choice, title="rco")
        cls.required_choice_option2 = RegistrationFieldOptionFactory(field=cls.required_choice, title="rco2")
        cls.required_choice_option_depends = RegistrationFieldOptionFactory(
            field=cls.required_choice, depends=cls.crew, title="rco_dep",
        )
        cls.depends_choice = RegistrationFieldFactory(
            event=cls.event, name="depends_choice", field_type=RegistrationField.types.CHOICE, depends=cls.crew,
            allow_change_days=1,
        )
        cls.depends_choice_option = RegistrationFieldOptionFactory(field=cls.depends_choice, title="dco")
        cls.depends_choice_option2 = RegistrationFieldOptionFactory(field=cls.depends_choice, title="dco2")

        # Add one more option to required_choice that depends on a field that has a depends itself
        cls.required_choice_option_depends_depends = RegistrationFieldOptionFactory(
            field=cls.required_choice, depends=cls.depends_choice_option2, title="rco_dep_dep",
        )

        cls.optional_string = RegistrationFieldFactory(
            event=cls.event, name="optional_string", field_type=RegistrationField.types.STRING, required=False,
            allow_change_days=1,
        )
        cls.required_string = RegistrationFieldFactory(
            event=cls.event, name="required_string", field_type=RegistrationField.types.STRING,
            allow_change_days=1,
        )
        cls.depends_string = RegistrationFieldFactory(
            event=cls.event, name="depends_string", field_type=RegistrationField.types.STRING, depends=cls.crew,
            allow_change_days=1,
        )
        cls.depends_depends_string = RegistrationFieldFactory(
            event=cls.event, name="depends_depends_str", field_type=RegistrationField.types.STRING,
            depends=cls.depends_choice_option2, allow_change_days=1,
        )

        cls.optional_text = RegistrationFieldFactory(
            event=cls.event, name="optional_text", field_type=RegistrationField.types.TEXT, required=False,
            allow_change_days=1,
        )
        cls.required_text = RegistrationFieldFactory(
            event=cls.event, name="required_text", field_type=RegistrationField.types.TEXT,
            allow_change_days=1,
        )
        cls.depends_text = RegistrationFieldFactory(
            event=cls.event, name="depends_text", field_type=RegistrationField.types.TEXT, depends=cls.crew,
            allow_change_days=1,
        )

        cls.optional_checkbox = RegistrationFieldFactory(
            event=cls.event, name="optional_checkbox", field_type=RegistrationField.types.CHECKBOX, required=False,
            allow_change_days=1,
        )
        cls.required_checkbox = RegistrationFieldFactory(
            event=cls.event, name="required_checkbox", field_type=RegistrationField.types.CHECKBOX,
            allow_change_days=1,
        )
        cls.depends_checkbox = RegistrationFieldFactory(
            event=cls.event, name="depends_checkbox", field_type=RegistrationField.types.CHECKBOX, depends=cls.crew,
            allow_change_days=1,
        )

        cls.optional_uncheckbox = RegistrationFieldFactory(
            event=cls.event, name="optional_uncheckbox", field_type=RegistrationField.types.UNCHECKBOX, required=False,
            allow_change_days=1,
        )
        cls.required_uncheckbox = RegistrationFieldFactory(
            event=cls.event, name="required_uncheckbox", field_type=RegistrationField.types.UNCHECKBOX,
            allow_change_days=1,
        )
        cls.depends_uncheckbox = RegistrationFieldFactory(
            event=cls.event, name="depends_uncheckbox", field_type=RegistrationField.types.UNCHECKBOX,
            depends=cls.crew, allow_change_days=1,
        )

        cls.optional_rating5 = RegistrationFieldFactory(
            event=cls.event, name="optional_rating5", field_type=RegistrationField.types.RATING5, required=False,
            allow_change_days=1,
        )
        cls.required_rating5 = RegistrationFieldFactory(
            event=cls.event, name="required_rating5", field_type=RegistrationField.types.RATING5,
            allow_change_days=1,
        )
        cls.depends_rating5 = RegistrationFieldFactory(
            event=cls.event, name="depends_rating5", field_type=RegistrationField.types.RATING5, depends=cls.crew,
            allow_change_days=1,
        )

        cls.optional_image = RegistrationFieldFactory(
            event=cls.event, name="optional_image", field_type=RegistrationField.types.IMAGE, required=False,
            allow_change_days=1,
        )
        cls.required_image = RegistrationFieldFactory(
            event=cls.event, name="required_image", field_type=RegistrationField.types.IMAGE,
            allow_change_days=1,
        )
        cls.depends_image = RegistrationFieldFactory(
            event=cls.event, name="depends_image", field_type=RegistrationField.types.IMAGE, depends=cls.crew,
            allow_change_days=1,
        )

    @property
    def test_image(self):
        # Minimal 1-pixel white gif, from https://cloudinary.com/blog/one_pixel_is_worth_three_thousand_words
        image = io.BytesIO(b'\x47\x49\x46\x38\x37\x61\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00'
                           + b'\xff\xff\xff\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
                           + b'img')
        image.name = 'white.gif'
        return image

    @property
    def test_image2(self):
        # Minimal 1-pixel transparent gif, from https://cloudinary.com/blog/one_pixel_is_worth_three_thousand_words
        image = io.BytesIO(b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00'
                           + b'\xff\xff\xff\x21\xf9\x04\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01'
                           + b'\x00\x00\x02\x02\x4c\x01\x00\x3b'
                           + b'img2')
        image.name = 'transparent.gif'
        return image

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    def assertFinalizeAllowed(self, response):
        self.assertHTML(response, 'input[name="agree"]')
        self.assertHTML(response, 'button[type="submit"]')

    def assertFinalizeNotAllowed(self, response, waiting=False):
        self.assertNotHTML(response, 'input[name="agree"]')
        self.assertNotHTML(response, 'input[type="submit"]')

    def assertFormRedirects(self, response, next_url):
        """ Check that a response from posting a form is succesful and redirects to the given url. """
        # 200 should not happen, but this improves the failure output when validation fails
        if response.status_code == 200:
            self.assertFalse(response.context['form'].errors)
        self.assertRedirects(response, next_url)

    def reverse_step(self, viewname, reg):
        args = (reg.pk,)
        if viewname in ('registrations:registration_start', 'registrations:edit_start'):
            args = (reg.event_id,)
        return reverse(viewname, args=args)

    def test_full_registration(self):
        """ Run through an entire registration flow. """
        e = self.event

        # Start step, should create a registration
        start_url = reverse('registrations:registration_start', args=(e.pk,))
        with self.assertTemplateUsed('registrations/registration_start.html'):
            self.client.get(start_url)

        response = self.client.post(start_url)
        reg = Registration.objects.get()
        next_url = self.reverse_step('registrations:step_registration_options', reg)
        self.assertFormRedirects(response, next_url)

        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        self.assertEqual(reg.event, e)
        self.assertEqual(reg.user, self.user)

        # Options step, should create options
        with self.assertTemplateUsed('registrations/step_registration_options.html'):
            self.client.get(next_url)

        data = {
            self.type.name: self.player.pk,
            self.gender.name: self.option_m.pk,
            self.origin.name: self.option_nl.pk,
            self.required_checkbox.name: "on",
            self.required_uncheckbox.name: "on",
            self.required_choice.name: self.required_choice_option.pk,
            self.required_image.name: self.test_image,
            self.required_rating5.name: "3",
            self.required_string.name: "abc",
            self.required_text.name: "xyz",
        }
        response = self.options_form_helper(reg, data)
        next_url = self.reverse_step('registrations:step_personal_details', reg)
        self.assertFormRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # Personal details step, should create Address and update user detail
        with self.assertTemplateUsed('registrations/step_personal_details.html'):
            self.client.get(next_url)

        data = {
            'user-first_name': 'foo',
            'user-last_name': 'bar',
            'address-phone_number': '+31101234567',
            'address-address': 'Some Street 123',
            'address-postalcode': '1234',
            'address-city': 'Town',
            'address-country': 'Country',
        }
        response = self.client.post(next_url, data)
        next_url = self.reverse_step('registrations:step_medical_details', reg)
        self.assertFormRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, data['user-first_name'])
        self.assertEqual(self.user.last_name, data['user-last_name'])
        addr = Address.objects.get()
        self.assertEqual(addr.phone_number, data['address-phone_number'])
        self.assertEqual(addr.address, data['address-address'])
        self.assertEqual(addr.postalcode, data['address-postalcode'])
        self.assertEqual(addr.city, data['address-city'])
        self.assertEqual(addr.country, data['address-country'])

        # Medical details step, should create MedicalDetails
        with self.assertTemplateUsed('registrations/step_medical_details.html'):
            self.client.get(next_url)

        data = {
            'food_allergies': 'foo',
            'event_risks': 'bar',
            'consent': True,
        }
        response = self.client.post(next_url, data)
        next_url = self.reverse_step('registrations:step_emergency_contacts', reg)
        self.assertFormRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        medical = MedicalDetails.objects.get()
        self.assertEqual(medical.food_allergies, data['food_allergies'])
        self.assertEqual(medical.event_risks, data['event_risks'])

        # Emergency contacts step, should create EmergencyContacts and update status
        with self.assertTemplateUsed('registrations/step_emergency_contacts.html'):
            self.client.get(next_url)

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
        response = self.client.post(next_url, data)
        next_url = self.reverse_step('registrations:step_final_check', reg)
        self.assertFormRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)
        first, second = EmergencyContact.objects.all().order_by('id')
        self.assertEqual(first.user, self.user)
        self.assertEqual(first.contact_name, data['emergency_contacts-0-contact_name'])
        self.assertEqual(first.relation, data['emergency_contacts-0-relation'])
        self.assertEqual(first.phone_number, data['emergency_contacts-0-phone_number'])
        self.assertEqual(first.remarks, data['emergency_contacts-0-remarks'])
        self.assertEqual(second.user, self.user)
        self.assertEqual(second.contact_name, data['emergency_contacts-1-contact_name'])
        self.assertEqual(second.relation, data['emergency_contacts-1-relation'])
        self.assertEqual(second.phone_number, data['emergency_contacts-1-phone_number'])
        self.assertEqual(second.remarks, data['emergency_contacts-1-remarks'])

        # Final check, should update status
        with self.assertTemplateUsed('registrations/step_final_check.html'):
            self.client.get(next_url)

        response = self.client.post(next_url, {'agree': 1})
        next_url = self.reverse_step('registrations:registration_confirmation', reg)
        self.assertFormRedirects(response, next_url)

        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    @parameterized.expand(itertools.product(
        Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    ))
    def test_change_options(self, status):
        """ Test that you can set options and then change them to different values, including empty. """
        reg = RegistrationFactory(event=self.event, user=self.user, status=status)

        history = {}

        # Set initial values for all fields
        data = {
            self.type.name: self.player.pk,
            self.gender.name: self.option_m.pk,
            self.origin.name: self.option_nl.pk,
            self.required_checkbox.name: "on",
            self.required_uncheckbox.name: "on",
            self.required_choice.name: self.required_choice_option.pk,
            self.required_rating5.name: "3",
            self.required_string.name: "abc",
            self.required_text.name: "xyz",
            self.optional_checkbox.name: "on",
            self.optional_choice.name: self.optional_choice_option.pk,
            self.optional_rating5.name: "2",
            self.optional_string.name: "def",
            self.optional_text.name: "ghi",
        }

        # Images are added separately, since they need not be resubmitted on every request, and the images are use-once
        # iterators.
        self.options_form_helper(reg, data | {
            self.required_image.name: self.test_image,
            self.optional_image.name: self.test_image2,
        }, history=history)

        # Then change all values (except for required checkboxes that have only one valid value)
        data.update({
            self.type.name: self.npc.pk,
            self.gender.name: self.option_f.pk,
            self.origin.name: self.option_intl.pk,
            self.required_choice.name: self.required_choice_option2.pk,
            self.required_rating5.name: "1",
            self.required_string.name: "ABC",
            self.required_text.name: "XYZ",
            self.optional_uncheckbox.name: "on",
            self.optional_choice.name: self.optional_choice_option2.pk,
            self.optional_rating5.name: "5",
            self.optional_string.name: "DEF",
            self.optional_text.name: "GHI",
        })
        del data[self.optional_uncheckbox.name]
        self.options_form_helper(reg, data | {
            self.required_image.name: self.test_image2,
            self.optional_image.name: self.test_image,
        }, history=history)

        # Test re-uploading the same images with the same data
        self.options_form_helper(reg, data | {
            self.required_image.name: self.test_image2,
            self.optional_image.name: self.test_image,
        }, history=history)

        # Test changing nothing
        self.options_form_helper(reg, data, check_data=data | {
            self.required_image.name: self.test_image2,
            self.optional_image.name: self.test_image,
        }, history=history)

        # Remove all optional values
        del data[self.optional_choice.name]
        del data[self.optional_rating5.name]
        del data[self.optional_string.name]
        del data[self.optional_text.name]

        self.options_form_helper(reg, data | {
            self.optional_image.name + "-clear": "on",
        }, check_data=data | {
            self.required_image.name: self.test_image2,
        }, history=history)

        # Set type=crew to unlock options that depend on that, and change them
        data.update({
            self.type.name: self.crew.pk,
        })
        depends_data = {
            self.depends_uncheckbox.name: "on",
            self.depends_checkbox.name: "on",
            self.depends_choice.name: self.depends_choice_option.pk,
            self.depends_rating5.name: "1",
            self.depends_string.name: "ABC",
            self.depends_text.name: "XYZ",
        }
        self.options_form_helper(reg, data | depends_data | {
            self.depends_image.name: self.test_image2,
        }, check_data=data | depends_data | {
            self.required_image.name: self.test_image2,
            self.depends_image.name: self.test_image2,
        }, history=history)

        # Set depends_choice=option2 to unlock depend_depend_string
        data.update({
            self.depends_choice.name: self.depends_choice_option2.pk,
        })
        depends_data.update({
            self.depends_depends_string.name: "def",
        })
        self.options_form_helper(reg, data | depends_data, check_data=data | depends_data | {
            self.required_image.name: self.test_image2,
            self.depends_image.name: self.test_image2,
        }, history=history)

        # And reset type to assert the dependent options are removed again, even when we do supply values for them
        # (options_form_helper checks this based on the type value).
        data.update({
            self.type.name: self.player.pk,
        })
        self.options_form_helper(reg, data | {
            self.depends_image.name: self.test_image2,
        }, check_data=data | {
            self.required_image.name: self.test_image2,
        }, history=history)

    def check_field_saved_helper(self, reg, value, data):
        """ Check that the given value is saved for the given registration and field, and value from the form data. """
        self.assertEqual(value.registration, reg)

        field = value.field

        submitted = data.get(field.name, "")
        string_value = ""
        file_value = None
        option = None

        # Check the saved value matches the submitted value
        if field.field_type.CHOICE:
            if submitted:
                option = RegistrationFieldOption.objects.get(pk=submitted)
        elif field.field_type.IMAGE:
            if submitted:
                file_value = submitted
        elif field.field_type.CHECKBOX or field.field_type.UNCHECKBOX:
            if submitted == "on":
                string_value = RegistrationFieldValue.CHECKBOX_VALUES[True]
            else:
                string_value = RegistrationFieldValue.CHECKBOX_VALUES[False]
        else:
            string_value = submitted

        msg = "for field: {}".format(repr(value.field))
        self.assertEqual(value.string_value, string_value, msg=msg)
        self.assertEqual(value.option, option, msg=msg)
        if file_value:
            self.assertEqual(value.file_value.read(), file_value.getvalue(), msg=msg)
        else:
            self.assertEqual(value.file_value.name, "", msg=msg)

    def check_field_rendered_helper(self, response, value, readonly):
        """ Check that the field for the given value is rendered in the form with the given value shown. """
        field = value.field
        if readonly:
            # Just assert that the span is present, figuring out what should be inside exactly is a hassle
            self.assertHTML(response, 'span[id="id_{}",class="spanwidget"]'.format(field.name))
        elif field.field_type.CHOICE:
            option = value.option
            if not value.option and field.required:
                option = field.options[0]
            if value.option:
                with self.assertHTML(response, 'select[name="{}"] option'.format(field.name)) as elems:
                    for elem in elems:
                        if option and elem.get('value') == str(value.option.pk):
                            self.assertIsNotNone(elem.get('selected'))
                        else:
                            self.assertIsNone(elem.get('selected'))
        elif field.field_type.IMAGE:
            if value.file_value:
                self.assertHTML(response, 'input[type="checkbox"][name="{}-clear"]'.format(field.name))
                with self.assertHTML(response, '#div_id_{}'.format(field.name)) as (elem,):
                    self.assertIn(_('Currently'), elem.text_content())
                    self.assertIn(value.file_value.name, elem.text_content())
            else:
                self.assertNotHTML(response, 'input[type="checkbox"][name="{}-clear"]'.format(field.name))
        elif field.field_type.CHECKBOX or field.field_type.UNCHECKBOX:
            if value.string_value == RegistrationFieldValue.CHECKBOX_VALUES[True]:
                with self.assertHTML(response, 'input[type="checkbox"][name="{}"]'.format(field.name)) as (elem,):
                    self.assertIsNotNone(elem.get('checked'))
            else:
                with self.assertHTML(response, 'input[type="checkbox"][name="{}"]'.format(field.name)) as (elem,):
                    self.assertIsNone(elem.get('checked'))
        else:
            if field.field_type.STRING:
                with self.assertHTML(response, 'input[type="text"][name="{}"]'.format(field.name)) as (elem,):
                    self.assertEqual(elem.get('value', ''), value.string_value)
            elif field.field_type.TEXT:
                with self.assertHTML(response, 'textarea[name="{}"]'.format(field.name)) as (elem,):
                    self.assertEqual(elem.text, '\n' + value.string_value)
            elif field.field_type.RATING5:
                with self.assertHTML(response, 'input[type="radio"][name="{}"]'.format(field.name)) as elems:
                    for elem in elems:
                        if elem.get('value') == value.string_value:
                            self.assertIsNotNone(elem.get('checked'))
                        else:
                            self.assertIsNone(elem.get('checked'))

    def options_form_helper(self, reg, data, check_data=None, readonly_fields=(), missing_fields=(), history=None):
        """ Submits the given data to the options form, and checks that it is saved correctly. """
        if check_data is None:
            check_data = data

        form_url = self.reverse_step('registrations:step_registration_options', reg)
        response = self.client.post(form_url, data)

        next_url = self.reverse_step('registrations:step_personal_details', reg)
        self.assertFormRedirects(response, next_url)

        values = list(RegistrationFieldValue.objects.only_active().order_by('field__name'))

        nondepends_fields = {
            self.type, self.gender, self.origin,
            self.optional_checkbox, self.optional_uncheckbox, self.optional_choice, self.optional_image,
            self.optional_rating5, self.optional_string, self.optional_text,
            self.required_checkbox, self.required_uncheckbox, self.required_choice, self.required_image,
            self.required_rating5, self.required_string, self.required_text,
        }
        depends_fields = {
            self.depends_checkbox, self.depends_uncheckbox, self.depends_choice, self.depends_image,
            self.depends_rating5, self.depends_string, self.depends_text,
        }
        depends_depends_fields = {
            self.depends_depends_string,
        }

        expected_values = set(nondepends_fields)
        if check_data[self.type.name] == self.crew.pk:
            expected_values.update(depends_fields)

            if check_data.get(self.depends_choice.name, None) == self.depends_choice_option2.pk:
                expected_values.update(depends_depends_fields)
        expected_values -= set(missing_fields)

        # Fields that depend on another option should be hidden when it is not selected and readonly
        expected_form_fields = set(nondepends_fields)
        if not (self.type in readonly_fields and check_data[self.type.name] != self.crew.pk):
            expected_form_fields.update(depends_fields)
        if not (self.depends_choice in readonly_fields
                and check_data[self.depends_choice.name] != self.depends_choice_option2.pk):
            expected_form_fields.update(depends_depends_fields)
        expected_form_fields -= set(missing_fields)

        self.assertEqual({v.field for v in values}, expected_values)

        for value in values:
            self.check_field_saved_helper(reg, value, check_data)

        if history is not None:
            self.inactive_options_helper(reg, history, values)

        form_response = self.client.get(form_url)
        for value in values:
            self.check_field_rendered_helper(form_response, value, readonly=(value.field in readonly_fields))

        # check_field_rendered_helper already checked if the values that were saved were actually rendered correctly,
        # this additionally checks that fields with unsatisfied dependencies are rendered and no extra fields are
        # rendered.
        with self.assertHTML(form_response, '.form-control, .form-control-file, .form-check-input') as elems:
            # Strip id_ prefix and rating options suffix
            id_re = re.compile(r'^id_(.+?)(_[0-9]*)?$')
            self.assertEqual(
                {id_re.sub(r'\1', e.get('id')) for e in elems},
                {f.name for f in expected_form_fields},
            )

        return response

    def inactive_options_helper(self, reg, history, active_values):
        """
        Helper to check active status of values.

        We need to check that editing active registrations produces new value objects (and makes the old ones
        inactive), while draft registrations can edit existing value objects.

        Since options_form_helper already checked the the list of active values contains the right fields and values,
        we only need to check:
         - that inactive values, and values of active registrations are never changed, and
         - new values always start out active

        The history object should be a dict (initially empty) that is passed to subsequent calls and will store some
        data between calls.
        """
        current_values = {
            v.pk: v
            for v in RegistrationFieldValue.objects.filter(registration=reg).select_related('field')
        }
        new_values = current_values.copy()

        for pk, prev in history.items():
            current = new_values.pop(pk, None)

            if reg.status.ACTIVE:
                self.assertIsNotNone(current, msg=f"Value unexpectedly deleted: {prev.field.name}={prev}")

            if reg.status.ACTIVE or not prev.active:
                msg = f"Value unexpectedly changed in database: pk={pk} name={current.field.name}"
                self.assertEqual(current.string_value, prev.string_value, msg=msg)
                self.assertEqual(current.option, prev.option, msg=msg)
                self.assertEqual(current.file_value, prev.file_value, msg=msg)
                self.assertEqual(current.file_value.name, prev.file_value.name, msg=msg)

        for new in new_values.values():
            # Newly created items must always be active
            self.assertEqual(new.active, True)

        history.clear()
        history.update(current_values)

    @parameterized.expand(itertools.product(
        Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    ))
    def test_missing_options(self, status):
        """ """
        e = self.event
        reg = RegistrationFactory(event=e, user=self.user, status=status)

        data = {
            self.type.name: self.player.pk,
            self.gender.name: self.option_m.pk,
            self.origin.name: self.option_nl.pk,
            self.required_checkbox.name: "on",
            self.required_uncheckbox.name: "on",
            self.required_choice.name: self.required_choice_option.pk,
            self.required_image.name: self.test_image,
            self.required_rating5.name: "3",
            self.required_string.name: "abc",
            self.required_text.name: "xyz",
        }
        next_url = self.reverse_step('registrations:step_registration_options', reg)

        for field_name in data:
            incomplete_data = data.copy()

            with self.subTest("Empty data for field should fail validation", field=field_name):
                incomplete_data[field_name] = ''
                response = self.client.post(next_url, incomplete_data)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['form'].is_valid())
                self.assertIn(field_name, response.context['form'].errors)

            with self.subTest("Omitted data for field should fail validation", field=field_name):
                incomplete_data.pop(field_name)
                response = self.client.post(next_url, incomplete_data)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['form'].is_valid())
                self.assertIn(field_name, response.context['form'].errors)

    @parameterized.expand(itertools.product(
        # Test both never-changeable and expired changeable options
        [None, (timezone.now() - timedelta(days=1)).date()],
        Registration.statuses.ACTIVE,
    ))
    def test_allow_change_until(self, until, status):
        """ Check that allow_change_until on a field is respected. """

        reg = RegistrationFactory(event=self.event, user=self.user, status=status)
        history = {}

        # Set initial values for all fields
        data = {
            self.type.name: self.player.pk,
            self.gender.name: self.option_m.pk,
            self.origin.name: self.option_nl.pk,
            self.required_checkbox.name: "on",
            self.required_uncheckbox.name: "on",
            self.required_choice.name: self.required_choice_option.pk,
            self.required_rating5.name: "3",
            self.required_string.name: "abc",
            self.required_text.name: "xyz",
            self.optional_checkbox.name: "on",
            self.optional_choice.name: self.optional_choice_option.pk,
            self.optional_rating5.name: "2",
            self.optional_string.name: "def",
            self.optional_text.name: "ghi",
        }
        self.options_form_helper(reg, data | {
            self.required_image.name: self.test_image,
            self.optional_image.name: self.test_image2,
        }, history=history)

        # Make a lot of options unchangeable, but keep required_choice editable so we can test
        # required_choice_option_depends
        unchangeable = [
            self.type,
            self.required_checkbox,
            self.required_uncheckbox,
            self.required_image,
            self.required_rating5,
            self.required_string,
            self.required_text,
            self.optional_uncheckbox,
            self.optional_checkbox,
            self.optional_choice,
            self.optional_image,
            self.optional_rating5,
            self.optional_string,
            self.optional_text,
        ]

        for o in RegistrationField.objects.filter(pk__in=[f.id for f in unchangeable]):
            o.allow_change_until = until
            o.save()

        # Then try to change all values (including for required checkboxes), and assert that unchangeable options are
        # not actually changed
        data.update({
            self.gender.name: self.option_f.pk,
            self.origin.name: self.option_intl.pk,
            self.required_choice.name: self.required_choice_option2.pk,
        })

        self.options_form_helper(reg, data | {
            self.type.name: self.npc.pk,
            self.required_image.name: self.test_image2,
            self.required_rating5.name: "1",
            self.required_string.name: "ABC",
            self.required_text.name: "XYZ",
            self.optional_uncheckbox.name: "on",
            self.optional_choice.name: self.optional_choice_option.pk,
            self.optional_image.name: self.test_image,
            self.optional_rating5.name: "5",
            self.optional_string.name: "DEF",
            self.optional_text.name: "GHI",
        }, check_data=data | {
            self.required_image.name: self.test_image,
            self.optional_image.name: self.test_image2,
        }, readonly_fields=unchangeable, history=history)

        # Make two unchangeable values inactive (including required), and check that the form still submits
        missing = (self.required_string, self.optional_string)
        for value in reg.options.filter(field__in=missing):
            value.active = None
            value.save()

        self.options_form_helper(reg, data, check_data=data | {
            self.required_image.name: self.test_image,
            self.optional_image.name: self.test_image2,
        }, readonly_fields=unchangeable, history=history, missing_fields=missing)

        # Set type=crew to unlock depends options
        type_value = reg.options.get(field=self.type, active=True)
        type_value.active = None
        type_value.save()
        RegistrationFieldValueFactory(registration=reg, option=self.crew)

        # Then try to set all depends values
        data.update({
            self.type.name: self.crew.pk,
            self.required_choice.name: self.required_choice_option_depends.pk,
            self.depends_uncheckbox.name: "on",
            self.depends_checkbox.name: "on",
            self.depends_choice.name: self.depends_choice_option.pk,
            self.depends_rating5.name: "1",
            self.depends_string.name: "ABC",
            self.depends_text.name: "XYZ",
        })

        self.options_form_helper(reg, data | {
            self.depends_image.name: self.test_image2,
            self.optional_image.name: self.test_image2,
        }, check_data=data | {
            self.required_image.name: self.test_image,
            self.depends_image.name: self.test_image2,
            self.optional_image.name: self.test_image2,
        }, readonly_fields=unchangeable, history=history, missing_fields=missing)

    @parameterized.expand(itertools.product(
        Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    ))
    def test_option_depends_not_satisfied(self, status):
        """ Test that using an option whose depends are not satisfied fails validation """
        e = self.event
        reg = RegistrationFactory(event=e, user=self.user, status=status)

        data = {
            self.type.name: self.player.pk,
            self.gender.name: self.option_m.pk,
            self.origin.name: self.option_nl.pk,
            self.required_checkbox.name: "on",
            self.required_uncheckbox.name: "on",
            self.required_choice.name: self.required_choice_option.pk,
            self.required_image.name: self.test_image,
            self.required_rating5.name: "3",
            self.required_string.name: "abc",
            self.required_text.name: "xyz",
        }
        next_url = self.reverse_step('registrations:step_registration_options', reg)

        with self.subTest("Option that depends on non-selected option should fail validation"):
            response = self.client.post(next_url, {
                **data,
                self.required_choice.name: self.required_choice_option_depends,
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['form'].is_valid())
            self.assertIn(self.required_choice.name, response.context['form'].errors)

        with self.subTest("Option that depends on field that depends on non-selected option should fail validation"):
            response = self.client.post(next_url, {
                **data,
                self.depends_choice.name: self.depends_choice_option2.pk,
                self.required_choice.name: self.required_choice_option_depends_depends.pk,
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['form'].is_valid())
            self.assertIn(self.required_choice.name, response.context['form'].errors)

    @parameterized.expand(itertools.product(
        # Test both never-changeable and expired changeable options
        [None, (timezone.now() - timedelta(days=1)).date()],
        edit_steps,
        Registration.statuses.ACTIVE,
    ))
    def test_event_allow_change_until(self, until, viewname, status):
        """ Check that allow_change_until on an event is respected. """

        reg = RegistrationFactory(event=self.event, user=self.user, status=status)
        reg.event.allow_change_until = until
        reg.event.save()

        start_url = self.reverse_step('registrations:edit_start', reg)
        url = self.reverse_step(viewname, reg)
        response = self.client.get(url)

        if url == start_url:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, start_url)

    def test_registration_sends_email(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        reg = RegistrationFactory(event=e, user=self.user, preparation_complete=True,
                                  options=[self.option_m, self.option_nl])
        check_url = self.reverse_step('registrations:step_final_check', reg)
        confirm_url = self.reverse_step('registrations:registration_confirmation', reg)
        response = self.client.post(check_url, {'agree': 1})
        self.assertFormRedirects(response, confirm_url)

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [reg.user.email])
        self.assertEqual(mail.outbox[0].bcc, settings.BCC_EMAIL_TO)
        self.assertNotIn('waiting', mail.outbox[0].subject.lower())
        self.assertNotEqual(mail.outbox[0].subject.lower(), "")
        self.assertNotEqual(mail.outbox[0].body, '')

    def test_waitinglist_registration_sends_email(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        # Fill up some slots
        for _i in range(2):
            RegistrationFactory(event=e, registered=True, options=[self.option_m, self.option_nl])

        # Then register on the waiting list
        reg = RegistrationFactory(event=e, user=self.user, preparation_complete=True,
                                  options=[self.option_m, self.option_nl])
        check_url = self.reverse_step('registrations:step_final_check', reg)
        confirm_url = self.reverse_step('registrations:registration_confirmation', reg)
        response = self.client.post(check_url, {'agree': 1})
        self.assertFormRedirects(response, confirm_url)

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [reg.user.email])
        self.assertEqual(mail.outbox[0].bcc, settings.BCC_EMAIL_TO)
        self.assertIn('waiting', mail.outbox[0].subject.lower())
        self.assertEqual(len(mail.outbox), 1)

    def test_pending_registration_sends_email(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.pending_mail_text = "MARKERMARKERMARKER"
        e.save()

        reg = RegistrationFactory(event=e, user=self.user, preparation_complete=True,
                                  options=[self.option_m, self.option_nl])
        check_url = self.reverse_step('registrations:step_final_check', reg)
        confirm_url = self.reverse_step('registrations:registration_confirmation', reg)
        response = self.client.post(check_url, {'agree': 1})
        self.assertFormRedirects(response, confirm_url)

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.statuses.PENDING)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [reg.user.email])
        self.assertEqual(mail.outbox[0].bcc, settings.BCC_EMAIL_TO)
        self.assertNotIn('waiting', mail.outbox[0].subject.lower())
        self.assertNotEqual(mail.outbox[0].subject.lower(), "")
        self.assertIn(e.pending_mail_text, mail.outbox[0].body)
        self.assertEqual(len(mail.outbox), 1)

    def test_registration_start(self):
        e = self.event
        start_url = reverse('registrations:registration_start', args=(e.pk,))
        with self.assertTemplateUsed('registrations/registration_start.html'):
            self.client.get(start_url)

        # Send a post request to start registration procedure, this should created a new Registration and redirect to
        # the next step.
        response = self.client.post(start_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        reg = Registration.objects.get(user=self.user, event=e)
        first_step_url = self.reverse_step('registrations:step_registration_options', reg)
        self.assertRedirects(response, first_step_url)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # Posting again should just redirect to the first step, and *not* create another Registration.
        response = self.client.post(start_url)
        self.assertRedirects(response, first_step_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # Getting should do the same
        response = self.client.get(start_url)
        self.assertRedirects(response, first_step_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)

        # One preparation is complete, getting it should redirect to finalcheck
        reg.status = Registration.statuses.PREPARATION_COMPLETE
        reg.save()
        final_check_url = self.reverse_step('registrations:step_final_check', reg)
        response = self.client.get(start_url)
        self.assertRedirects(response, final_check_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)

        # And posting again should now redirect to final_check, without creating a new Registration or modifying the
        # status.
        response = self.client.post(start_url)
        self.assertRedirects(response, final_check_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)

        # And if registered, getting it should redirect to the confirmation
        reg.status = Registration.statuses.REGISTERED
        reg.registered_at = timezone.now()
        reg.save()
        confirmation_url = self.reverse_step('registrations:registration_confirmation', reg)
        response = self.client.get(start_url)
        self.assertRedirects(response, confirmation_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        # And posting again should now redirect to confirmation, without creating a new Registration or modifying the
        # status.
        response = self.client.post(start_url)
        self.assertRedirects(response, confirmation_url)
        self.assertEqual(Registration.objects.all().count(), 1)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    @parameterized.expand(all_steps_except_start)
    def test_others_registration(self, viewname):
        """ Check that all registration steps fail with someone else's registration. """
        registration = RegistrationFactory(event=self.event)

        url = self.reverse_step(viewname, registration)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    @parameterized.expand(itertools.product(
        all_steps,
        Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    ))
    def test_own_registration(self, viewname, status):
        """ Check that all registration steps load with your own registration. """
        registration = RegistrationFactory(event=self.event, user=self.user, status=status)

        url = self.reverse_step(viewname, registration)
        response = self.client.get(url)
        expected_status = 200
        if not status.PREPARATION_COMPLETE and viewname == 'registrations:step_final_check':
            expected_status = 302
        elif viewname == 'registrations:registration_start':
            expected_status = 302
        if not status.ACTIVE and viewname in self.edit_steps and viewname not in self.registration_steps:
            expected_status = 302
        self.assertEqual(response.status_code, expected_status)

        # Do not test POST, since that might not work reliably (e.g. the emergency contacts formset breaks for lack
        # of a management form).

    @parameterized.expand(all_steps_except_start)
    def test_canceled_registration(self, viewname):
        """ Check that all registration steps reject a canceled registration """
        registration = RegistrationFactory(event=self.event, user=self.user, cancelled=True)

        url = self.reverse_step(viewname, registration)
        # Follow, since some views redirect to final which 404s
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 404)

    @parameterized.expand(itertools.product(
        Registration.statuses.ACTIVE))
    def test_active_registration(self, status):
        """ Check that finalcheck for active registrations redirect to the registration completed page """
        viewname = 'registrations:step_final_check'
        registration = RegistrationFactory(event=self.event, user=self.user, status=status)

        url = self.reverse_step(viewname, registration)
        confirm_url = self.reverse_step('registrations:registration_confirmation', registration)
        # Follow, since some views redirect to final which 404s
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, confirm_url)

        response = self.client.post(url, follow=True)
        self.assertRedirects(response, confirm_url)

    @parameterized.expand(itertools.product(
        Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    ))
    def test_not_logged_in(self, status):
        """ Check that the registration steps redirect when not logged in. """
        def test_view(view, reg):
            url = self.reverse_step(view, reg)
            with self.subTest(view=view, method='GET'):
                # Follow to redirect to the login page so we can check resolver_match
                response = self.client.get(url, follow=True)
                self.assertEqual(response.resolver_match.url_name, 'account_login')

            with self.subTest(view=view, method='POST'):
                # Follow to redirect to the login page so we can check resolver_match
                # This posts without data, since we should be redirected anyway
                response = self.client.post(url, follow=True)
                self.assertEqual(response.resolver_match.url_name, 'account_login')

        self.client.logout()
        registration = RegistrationFactory(event=self.event, user=self.user, status=status)

        test_view('registrations:registration_start', registration)
        for view in self.all_steps:
            test_view(view, registration)

    def test_registration_opens(self):
        """ Check that finalcheck is closed until the right time and then opens. """
        reg = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)
        opens_at = self.event.registration_opens_at
        before_opens_at = opens_at - timedelta(seconds=1)
        final_check_url = self.reverse_step('registrations:step_final_check', reg)
        confirm_url = self.reverse_step('registrations:registration_confirmation', reg)

        with mock.patch('django.utils.timezone.now', return_value=before_opens_at):
            response = self.client.get(final_check_url)
            self.assertFinalizeNotAllowed(response)
            self.assertFalse(response.context['event'].registration_is_open)

            response = self.client.post(final_check_url, {'agree': 1}, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['event'].registration_is_open)
            reg.refresh_from_db()
            self.assertFalse(reg.status.REGISTERED)

        with mock.patch('django.utils.timezone.now', return_value=opens_at):
            response = self.client.get(final_check_url)
            self.assertFinalizeAllowed(response)
            self.assertTrue(response.context['event'].registration_is_open)

            response = self.client.post(final_check_url, {'agree': 1})
            self.assertFormRedirects(response, confirm_url)
            reg.refresh_from_db()
            self.assertTrue(reg.status.REGISTERED)

    def test_registration_closes(self):
        """ Check that finalcheck regenerates a response after registration opens. """
        reg = RegistrationFactory(event=self.event, user=self.user, preparation_complete=True)
        start_date_midnight = timezone.make_aware(datetime.combine(self.event.start_date, dt_time.min))
        before_start_date = start_date_midnight - timedelta(seconds=1)
        final_check_url = self.reverse_step('registrations:step_final_check', reg)
        confirm_url = self.reverse_step('registrations:registration_confirmation', reg)

        with mock.patch('django.utils.timezone.now', return_value=before_start_date):
            response = self.client.get(final_check_url)
            self.assertFinalizeAllowed(response)
            self.assertTrue(response.context['event'].registration_is_open)

            response = self.client.post(final_check_url, {'agree': 1})
            self.assertFormRedirects(response, confirm_url)
            reg.refresh_from_db()
            self.assertTrue(reg.status.REGISTERED)

        reg.status = Registration.statuses.PREPARATION_COMPLETE
        reg.save()

        with mock.patch('django.utils.timezone.now', return_value=start_date_midnight):
            response = self.client.get(final_check_url, follow=True)
            self.assertEqual(response.status_code, 404)

            response = self.client.post(final_check_url, {'agree': 1}, follow=True)
            self.assertEqual(response.status_code, 404)
            reg.refresh_from_db()
            self.assertFalse(reg.status.REGISTERED)

    @parameterized.expand(registration_steps)
    @skip("Conflict check disabled until improved")
    def test_other_event_redirect_to_finalcheck(self, viewname):
        """ Check that all registration steps redirect to finalcheck when registered for another event. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)
        RegistrationFactory(user=self.user, event=e2, registered=True)
        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)

        url = self.reverse_step(viewname, reg)
        conflict_url = self.reverse_step('registrations:conflicting_registrations', reg)

        with self.subTest(method='GET'):
            response = self.client.get(url)
            self.assertRedirects(response, conflict_url)

        with self.subTest(method='GET'):
            response = self.client.post(url)
            self.assertRedirects(response, conflict_url)

    @skip("Conflict check disabled until improved")
    def test_register_two_events(self):
        """ Check that you can only register for one event. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration
        RegistrationFactory(user=self.user, event=e2, registered=True)

        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)
        final_check_url = self.reverse_step('registrations:step_final_check', reg)
        conflict_url = self.reverse_step('registrations:conflicting_registrations', reg)

        # Causes second registration to be refused on GET
        response = self.client.get(final_check_url)
        with self.subTest(msg="Should redirect"):
            self.assertRedirects(response, conflict_url)

        # Causes second registration to be refused on POST
        response = self.client.post(final_check_url, {'agree': 1})
        with self.subTest(msg="Should redirect"):
            self.assertRedirects(response, conflict_url)
        with self.subTest(msg="Should not set status"):
            reg.refresh_from_db()
            self.assertTrue(reg.status.PREPARATION_COMPLETE)

    @skip("Conflict check disabled until improved")
    def test_register_two_events_between_view_and_service(self):
        """ Check that a second registration is refused, even when the first one happens late. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)
        other_reg = RegistrationFactory(user=self.user, event=e2, registered=True)

        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)
        final_check_url = self.reverse_step('registrations:step_final_check', reg)
        conflict_url = self.reverse_step('registrations:conflicting_registrations', reg)

        # Make an existing registration just before the service finalizes. This should *not* run inside the services'
        # transaction, after the lock, since that would deadlock (that would need threading and more coordination (that
        # would need threading and more coordination).
        # TODO: Can we write this more concise?
        def before_finalize(*args, **kwargs):
            other_reg.status.REGISTERED = True
            other_reg.save()

            # Let the original function also run
            return mock.DEFAULT

        with mock.patch(
            'apps.registrations.services.RegistrationStatusService.finalize_registration',
            side_effect=before_finalize,
            wraps=RegistrationStatusService.finalize_registration,
        ):
            response = self.client.post(final_check_url, {'agree': 1})
            with self.subTest(msg="Should redirect"):
                self.assertRedirects(response, conflict_url)
            with self.subTest(msg="Should not set status"):
                reg.refresh_from_db()
                self.assertTrue(reg.status.PREPARATION_COMPLETE)

    def test_register_second_after_waiting_list(self):
        """ Check that you can still register for a second event after a waitinglist registration. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration on the waitinglist
        RegistrationFactory(user=self.user, event=e2, waiting_list=True)

        # Does not prevent another registration on GET
        reg = RegistrationFactory(user=self.user, event=e, preparation_complete=True)
        final_check_url = self.reverse_step('registrations:step_final_check', reg)
        confirm_url = self.reverse_step('registrations:registration_confirmation', reg)
        response = self.client.get(final_check_url)
        with self.subTest(msg="Should show finalcheck with form"):
            self.assertTemplateUsed(response, FinalCheck.template_name)
            self.assertFinalizeAllowed(response)
        with self.subTest(msg="Should not set status"):
            self.assertTrue(reg.status.PREPARATION_COMPLETE)

        # Does not prevent another registration on POST
        response = self.client.post(final_check_url, {'agree': 1})
        with self.subTest(msg="Should redirect"):
            self.assertRedirects(response, confirm_url)
        with self.subTest(msg="Should set status"):
            reg.refresh_from_db()
            self.assertTrue(reg.status.REGISTERED)
