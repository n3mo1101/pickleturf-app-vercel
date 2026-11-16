from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class HomeRoutingTests(TestCase):

    def setUp(self):
        self.url = reverse('core:home')

    def test_guest_sees_landing_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/landing.html')

    def test_customer_sees_customer_home(self):
        customer = User.objects.create_user(
            email='customer@example.com',
            password='securepass123',
            first_name='Customer',
            last_name='User',
        )
        self.client.force_login(customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/customer_home.html')

    def test_admin_redirected_to_dashboard(self):
        admin = User.objects.create_user(
            email='admin@example.com',
            password='securepass123',
            first_name='Admin',
            last_name='User',
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_staff_redirected_to_dashboard(self):
        staff = User.objects.create_user(
            email='staff@example.com',
            password='securepass123',
            first_name='Staff',
            last_name='User',
            role=User.Role.STAFF,
        )
        self.client.force_login(staff)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard:index'))
