import itertools

from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from reversion.models import Revision
from with_asserts.mixin import AssertHTMLMixin

from apps.core.models import ConsentLog
from apps.people.models import ArtaUser
from apps.people.tests.factories import ArtaUserFactory

from .test_account_creation import CONSENT_COMBOS, CONSENT_PREFS


class TestEmailPreferencesForm(TestCase, AssertHTMLMixin):
    def setUp(self):
        self.user = ArtaUserFactory()
        self.client.force_login(self.user)

    @parameterized.expand(itertools.product(CONSENT_COMBOS, CONSENT_COMBOS))
    def test_change_consent_announcments(self, old_values, new_values):
        """ Check that changing settings. """

        self.user.refresh_from_db()
        for attr, value in old_values:
            setattr(self.user, attr, value)
        self.user.save()

        form_url = reverse('core:email_prefs')
        with self.assertTemplateUsed('core/email_preferences.html'):
            response = self.client.get(form_url)

        for attr, value in old_values:
            with self.subTest(attr=attr):
                with self.assertHTML(response, 'input[type="checkbox"][name="{}"]'.format(attr)) as (elem,):
                    if value:
                        self.assertIsNotNone(elem.get('checked'))
                    else:
                        self.assertIsNone(elem.get('checked'))

        data = dict(new_values)

        response = self.client.post(form_url, data)
        self.assertRedirects(response, form_url)

        # Check that a user was created
        self.user.refresh_from_db()

        for attr, value in new_values:
            with self.subTest(attr=attr):
                self.assertEqual(getattr(self.user, attr), value)

        # Check that consent was logged
        logs = {log.consent_name: log for log in ConsentLog.objects.all()}
        any_modified = False
        for (attr, old_value), (attr2, new_value) in zip(old_values, new_values):
            with self.subTest(attr=attr):
                self.assertEqual(attr, attr2)  # Sanity check of parameterized input

                if old_value != new_value:
                    any_modified = True
                    # Check that consent was logged
                    consent_name = CONSENT_PREFS[attr]
                    log = logs.pop(consent_name, None)
                    self.assertIsNotNone(log, msg="ConsentLog instance should be created")
                    self.assertEqual(log.user, self.user)
                    self.assertEqual(log.consent_name, consent_name)
                    if new_value:
                        self.assertEqual(log.action, ConsentLog.actions.CONSENTED)
                    else:
                        self.assertEqual(log.action, ConsentLog.actions.WITHDRAWN)

        # Check that no additional consent was logged
        self.assertFalse(logs, msg="No additional ConsentLog instances should be created")

        if any_modified:
            # Check a revision was created
            revision = Revision.objects.get()
            version = revision.version_set.get()
            self.assertEqual(version.content_type.model_class(), ArtaUser)
