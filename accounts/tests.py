# accounts/tests.py

import re
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from allauth.account.models import EmailAddress
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from accounts.management.commands.preview_emails import Command as PreviewEmails

User = get_user_model()


class UserModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='securepass123',
            first_name='John',
            last_name='Doe',
        )

    def test_user_created_with_customer_role(self):
        self.assertEqual(self.user.role, User.Role.CUSTOMER)

    def test_full_name_property(self):
        self.assertEqual(self.user.full_name, 'John Doe')

    def test_is_admin_or_staff_false_for_customer(self):
        self.assertFalse(self.user.is_admin_or_staff)

    def test_is_admin_or_staff_true_for_admin(self):
        admin = User.objects.create_user(
            email='admin@example.com',
            password='pass',
            first_name='Admin',
            last_name='User',
            role='admin',
        )
        self.assertTrue(admin.is_admin_or_staff)

    def test_is_admin_or_staff_true_for_staff(self):
        staff = User.objects.create_user(
            email='staff@example.com',
            password='pass',
            first_name='Staff',
            last_name='User',
            role='staff',
        )
        self.assertTrue(staff.is_admin_or_staff)

    def test_superuser_creation(self):
        su = User.objects.create_superuser(
            email='super@example.com',
            password='superpass',
            first_name='Super',
            last_name='User',
        )
        self.assertTrue(su.is_superuser)
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_active)

    def test_email_used_as_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')

    def test_email_must_be_unique(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email='test@example.com',  # duplicate
                password='pass',
                first_name='Dup',
                last_name='User',
            )


class LoginPageTests(TestCase):

    def setUp(self):
        self.url = reverse('account_login')

    def test_login_field_labelled_username_or_email(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('Username or email', html)

    def test_login_inputs_have_no_placeholders(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('placeholder="Username or email"', html)
        self.assertNotIn('placeholder="Password"', html)

    def test_single_password_reset_link(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('Forgot your password?', html)
        self.assertEqual(html.count('Forgot password?'), 1)


@override_settings(ACCOUNT_EMAIL_VERIFICATION='mandatory')
class EmailVerificationTests(TestCase):

    SIGNUP_DATA = {
        'first_name':    'New',
        'last_name':     'Customer',
        'email':         'new@example.com',
        'phone':         '',
        'password1':     'securepass123',
        'password2':     'securepass123',
    }

    def setUp(self):
        # allauth rate-limits verification mails per address (3 min), and the
        # cache outlives a test.
        cache.clear()

    def signup(self, **overrides):
        data = {**self.SIGNUP_DATA, **overrides}
        return self.client.post(reverse('account_signup'), data)

    def confirmation_path(self, body):
        url = re.search(r'https?://\S+', body).group(0).rstrip('.')
        return urlparse(url).path

    def test_signup_sends_confirmation_and_keeps_user_signed_out(self):
        response = self.signup()

        self.assertRedirects(
            response,
            reverse('account_email_verification_sent'),
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/confirm-email/', mail.outbox[0].body)
        self.assertIn('expires in 24 hours', mail.outbox[0].body)
        self.assertNotIn('_auth_user_id', self.client.session)

        user = User.objects.get(email='new@example.com')
        self.assertFalse(EmailAddress.objects.get(user=user).verified)

    def test_confirming_email_verifies_it_and_logs_in(self):
        self.signup()
        path = self.confirmation_path(mail.outbox[0].body)

        response = self.client.get(path)

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='new@example.com')
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertIn('_auth_user_id', self.client.session)

    def test_unverified_user_cannot_log_in(self):
        user = User.objects.create_user(
            email='pending@example.com',
            password='securepass123',
            first_name='Pending',
            last_name='User',
        )
        EmailAddress.objects.create(
            user=user, email='pending@example.com', primary=True, verified=False
        )

        response = self.client.post(reverse('account_login'), {
            'login':    'pending@example.com',
            'password': 'securepass123',
        })

        self.assertRedirects(
            response,
            reverse('account_email_verification_sent'),
            fetch_redirect_response=False,
        )
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_verified_user_can_log_in(self):
        user = User.objects.create_user(
            email='verified@example.com',
            password='securepass123',
            first_name='Verified',
            last_name='User',
        )
        EmailAddress.objects.create(
            user=user, email='verified@example.com', primary=True, verified=True
        )

        response = self.client.post(reverse('account_login'), {
            'login':    'verified@example.com',
            'password': 'securepass123',
        })

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.client.session)


class MarkEmailsVerifiedCommandTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='legacy@example.com',
            password='securepass123',
            first_name='Legacy',
            last_name='User',
        )
        EmailAddress.objects.create(
            user=self.user, email='legacy@example.com', primary=True, verified=False
        )

    def run_command(self, *args):
        call_command('mark_emails_verified', *args, stdout=StringIO())

    def test_marks_existing_addresses_verified(self):
        self.run_command()
        self.assertTrue(EmailAddress.objects.get(user=self.user).verified)

    def test_dry_run_does_not_change_anything(self):
        self.run_command('--dry-run')
        self.assertFalse(EmailAddress.objects.get(user=self.user).verified)

    def test_command_is_idempotent(self):
        self.run_command()
        self.run_command()
        self.assertTrue(EmailAddress.objects.get(user=self.user).verified)


class EmailDesignTests(TestCase):

    SIGNUP_DATA = {
        'first_name': 'Design',
        'last_name':  'Check',
        'phone':      '',
        'password1':  'securepass123',
        'password2':  'securepass123',
    }

    def setUp(self):
        cache.clear()

    def signup(self, email):
        return self.client.post(
            reverse('account_signup'), {'email': email, **self.SIGNUP_DATA}
        )

    def html_part(self, message):
        self.assertTrue(message.alternatives, 'email has no HTML alternative')
        body, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        return body

    def make_user(self, email='notify@example.com'):
        user = User.objects.create_user(
            email=email,
            password='securepass123',
            first_name='Notify',
            last_name='User',
        )
        EmailAddress.objects.create(
            user=user, email=email, primary=True, verified=True
        )
        return user

    @override_settings(ACCOUNT_EMAIL_VERIFICATION='mandatory')
    def test_confirmation_email_is_branded_html(self):
        self.signup('brand.new@example.com')

        message = mail.outbox[0]
        html = self.html_part(message)

        self.assertEqual(message.subject, 'Confirm your PickleTurf account')
        self.assertIn('Confirm my email', html)
        self.assertIn('/accounts/confirm-email/', html)
        self.assertIn('expires in 24 hours', html)
        self.assertIn('Pickle<span style="color:#F5C518;">Turf</span>', html)

    def test_password_reset_email_is_branded_html(self):
        user = self.make_user('reset.me@example.com')

        self.client.post(reverse('account_reset_password'), {'email': user.email})

        html = self.html_part(mail.outbox[-1])
        self.assertIn('Choose a new password', html)
        self.assertIn('/accounts/password/reset/key/', html)

    def test_duplicate_signup_sends_branded_account_exists_email(self):
        self.make_user('taken@example.com')

        self.signup('taken@example.com')

        message = mail.outbox[-1]
        self.assertEqual(message.subject, 'You already have a PickleTurf account')
        self.assertIn('You already have an account', self.html_part(message))

    def test_unknown_account_email_is_branded_html(self):
        self.client.post(
            reverse('account_reset_password'), {'email': 'nobody@example.com'}
        )

        html = self.html_part(mail.outbox[-1])
        self.assertIn("couldn't find that account", html)
        self.assertIn('Create an account', html)

    def test_password_change_notification_has_absolute_reset_link(self):
        user = self.make_user()
        self.client.force_login(user)

        self.client.post(
            reverse('account_change_password'),
            {
                'oldpassword': 'securepass123',
                'password1': 'brandnewpass456',
                'password2': 'brandnewpass456',
            },
        )

        message = mail.outbox[-1]
        self.assertEqual(message.subject, 'Your PickleTurf password was changed')
        html = self.html_part(message)
        self.assertIn('Your password was changed', html)

        # The "reset it" CTA must be a full URL the mail client can open.
        reset_url = re.search(r'href="(http[^"]*password/reset[^"]*)"', html)
        self.assertIsNotNone(reset_url)
        self.assertTrue(reset_url.group(1).startswith('http://'))

    def test_every_email_template_renders(self):
        context = PreviewEmails().context()
        names = [name for name, _ in PreviewEmails.TEMPLATES]
        names += [name.replace('.html', '.txt') for name, _ in PreviewEmails.TEMPLATES]

        for name in names:
            with self.subTest(template=name):
                self.assertTrue(render_to_string(name, context).strip())

    def test_preview_command_writes_files(self):
        with TemporaryDirectory() as tmp:
            call_command('preview_emails', output=tmp, stdout=StringIO())

            index = Path(tmp) / 'index.html'
            self.assertTrue(index.exists())
            self.assertTrue((Path(tmp) / 'confirmation.html').exists())

