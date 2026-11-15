"""Query-count regression tests for the hot, list-heavy views.

Each test renders the same page twice with a larger dataset and asserts the
query count does not grow. That catches reintroduced N+1s without pinning
brittle absolute numbers (which change with template tweaks).
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from bookings.services import create_booking
from courts.models import Court
from inventory.models import Category, InventoryItem
from openplay.models import OpenPlayParticipant, OpenPlaySession

User = get_user_model()


class QueryCountTestCase(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff@perf.test',
            password='testpass123',
            first_name='Staff',
            last_name='User',
            role='staff',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            email='customer@perf.test',
            password='testpass123',
            first_name='Test',
            last_name='Customer',
        )
        self.court = Court.objects.create(name='Court 1', is_active=True)
        self.tomorrow = date.today() + timedelta(days=1)
        self._booking_day_offset = 0

    def _query_count(self, url, user):
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(captured.captured_queries)

    def _make_sessions(self, count):
        for index in range(count):
            session = OpenPlaySession.objects.create(
                title=f'Session {index}',
                date=self.tomorrow + timedelta(days=index),
                start_time=time(9, 0),
                end_time=time(11, 0),
                capacity=10,
                fee=0,
            )
            OpenPlayParticipant.objects.create(
                session=session,
                user=None,
                participant_name=f'Walk-in {index}',
                status=OpenPlayParticipant.Status.APPROVED,
            )

    def _make_bookings(self, count):
        # `create_booking` already creates the matching (pending) transaction.
        for _ in range(count):
            self._booking_day_offset += 1
            create_booking(
                user=self.customer,
                court=self.court,
                selected_date=self.tomorrow + timedelta(
                    days=self._booking_day_offset
                ),
                start_time=time(9, 0),
            )


class OpenPlayAdminListQueryTests(QueryCountTestCase):

    def test_query_count_is_constant(self):
        self._make_sessions(1)
        baseline = self._query_count(reverse('openplay:admin_list'), self.staff)

        self._make_sessions(5)
        expanded = self._query_count(reverse('openplay:admin_list'), self.staff)

        self.assertEqual(baseline, expanded)


class MyBookingsQueryTests(QueryCountTestCase):

    def test_query_count_is_constant(self):
        self._make_bookings(1)
        baseline = self._query_count(reverse('bookings:my_bookings'), self.customer)

        self._make_bookings(4)
        expanded = self._query_count(reverse('bookings:my_bookings'), self.customer)

        self.assertEqual(baseline, expanded)


class ShopQueryTests(QueryCountTestCase):

    def test_query_count_is_constant(self):
        category = Category.objects.create(name='Paddles')
        InventoryItem.objects.create(
            category=category,
            name='Paddle A',
            item_type=InventoryItem.ItemType.SALE,
            sale_price=1000,
            stock=3,
        )
        baseline = self._query_count(reverse('inventory:shop'), self.customer)

        for index in range(6):
            InventoryItem.objects.create(
                category=category,
                name=f'Paddle {index}',
                item_type=InventoryItem.ItemType.SALE,
                sale_price=1000,
                stock=3,
            )
        expanded = self._query_count(reverse('inventory:shop'), self.customer)

        self.assertEqual(baseline, expanded)


class DashboardQueryTests(QueryCountTestCase):

    def test_query_count_is_constant(self):
        self._make_sessions(1)
        baseline = self._query_count(reverse('dashboard:index'), self.staff)

        self._make_sessions(4)
        expanded = self._query_count(reverse('dashboard:index'), self.staff)

        self.assertEqual(baseline, expanded)
