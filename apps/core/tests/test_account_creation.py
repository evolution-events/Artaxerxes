import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from reversion.models import Revision

from apps.core.models import ConsentLog
from apps.people.models import ArtaUser


class TestCreationForm(TestCase):
    consent_name = 'email_announcements'

    @parameterized.expand([(True,), (False,)])
    def test_registration(self, consent):
        """ Check that registering an account works. """

        signup_url = reverse('account_signup')
        confirmation_sent_url = reverse('account_email_verification_sent')
        with self.assertTemplateUsed('account/signup.html'):
            self.client.get(signup_url)

        data = {
            'email': 'info@example.org',
            'first_name': 'first',
            'last_name': 'last',
            'consent_announcements': consent,
            'password1': 'password',
            'password2': 'password',
        }
        response = self.client.post(signup_url, data)
        self.assertRedirects(response, confirmation_sent_url)

        # Check that a user was created
        user = ArtaUser.objects.get()
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.first_name, data['first_name'])
        self.assertEqual(user.last_name, data['last_name'])
        self.assertTrue(user.check_password(data['password1']))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.consent_announcements, consent)

        # Check that consent was logged
        if consent:
            log = ConsentLog.objects.get()
            self.assertEqual(log.user, user)
            self.assertEqual(log.action, ConsentLog.actions.CONSENTED)
            self.assertEqual(log.consent_name, self.consent_name)

        # Check an unverified e-mail address was added
        email = user.emailaddress_set.get()
        self.assertEqual(email.email, user.email)
        self.assertFalse(email.verified)
        self.assertTrue(email.primary)

        # Check a revision was created
        revision = Revision.objects.get()
        version = revision.version_set.get()
        self.assertEqual(version.content_type.model_class(), ArtaUser)

        # Check that a confiration mail was sent with a confirm url
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertEqual(mail.outbox[0].bcc, [])
        # This hardcodes a bit of the link to find it, would be nicer to use the url pattern by name instead
        match = re.search("https?://[^ ]*/confirm-email/[^/]*/", mail.outbox[0].body)
        self.assertIsNotNone(match, msg="Email should contain confirm link")
        confirm_url = match[0]

        # TODO: Check that user cannot login

        with self.assertTemplateUsed('account/email_confirm.html'):
            self.client.get(confirm_url)

        response = self.client.post(confirm_url)
        self.assertEqual(response.status_code, 302)

        # Check that email is now verified
        email.refresh_from_db()
        self.assertTrue(email.verified)

        # TODO: Check that user can now login

    # TODO: Failure tests: Too short password, invalid e-mail address, missing name fields
