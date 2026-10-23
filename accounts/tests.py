# accounts/tests.py

from django.test import TestCase
from django.contrib.auth import get_user_model

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