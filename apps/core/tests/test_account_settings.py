from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from reversion.models import Revision
from with_asserts.mixin import AssertHTMLMixin

from apps.core.models import ConsentLog
from apps.people.models import ArtaUser
from apps.people.tests.factories import ArtaUserFactory


class TestRegistrationForm(TestCase, AssertHTMLMixin):
    consent_name = 'email_announcements'
    field_name = 'consent_announcements'

    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    @parameterized.expand([
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ])
    def test_change_consent_announcments(self, old_value, new_value):
        """ Check that changing settings. """

        self.user.refresh_from_db()
        self.user.consent_announcements = old_value
        self.user.save()

        form_url = reverse('core:email_prefs')
        with self.assertTemplateUsed('core/email_preferences.html'):
            response = self.client.get(form_url)

        with self.assertHTML(response, 'input[type="checkbox"][name="{}"]'.format(self.field_name)) as (elem,):
            if old_value:
                self.assertIsNotNone(elem.get('checked'))
            else:
                self.assertIsNone(elem.get('checked'))

        data = {
            self.field_name: new_value,
        }
        response = self.client.post(form_url, data)
        self.assertRedirects(response, form_url)

        # Check that a user was created
        self.user.refresh_from_db()

        self.assertEqual(self.user.consent_announcements, new_value)

        if old_value != new_value:
            # Check that consent was logged
            log = ConsentLog.objects.get()
            self.assertEqual(log.user, self.user)
            self.assertEqual(log.consent_name, self.consent_name)
            if new_value:
                self.assertEqual(log.action, ConsentLog.actions.CONSENTED)
            else:
                self.assertEqual(log.action, ConsentLog.actions.WITHDRAWN)

            # Check a revision was created
            revision = Revision.objects.get()
            version = revision.version_set.get()
            self.assertEqual(version.content_type.model_class(), ArtaUser)
        else:
            self.assertEqual(ConsentLog.objects.count(), 0, msg="No ConsentLog should be created")
