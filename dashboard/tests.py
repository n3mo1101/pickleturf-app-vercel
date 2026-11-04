from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from courts.models import Court
from transactions.models import Transaction

from dashboard.views import _format_duration


class ExportCsvTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='pass12345',
            first_name='Admin', last_name='One',
        )
        self.admin.role = User.Role.ADMIN
        self.admin.save()
        self.url = reverse('dashboard:export_csv')

    def _login(self):
        self.client.login(email='admin@example.com', password='pass12345')

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(self.url, {'type': 'transactions'})
        self.assertEqual(resp.status_code, 302)

    def test_invalid_type_returns_400(self):
        self._login()
        resp = self.client.get(self.url, {'type': 'nope'})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_dates_return_400(self):
        self._login()
        resp = self.client.get(self.url, {
            'type': 'transactions', 'start': 'bad', 'end': 'bad',
        })
        self.assertEqual(resp.status_code, 400)

    def test_transactions_export(self):
        self._login()
        Transaction.objects.create(
            tx_type=Transaction.TxType.SALE,
            amount=150,
            description='Item sale',
        )
        resp = self.client.get(self.url, {'type': 'transactions'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn(
            'transactions_all.csv', resp['Content-Disposition'])
        lines = resp.content.decode().strip().splitlines()
        self.assertEqual(
            lines[0],
            'ID,Date,Type,Amount,Payment Status,Description,Slots,Created By')
        self.assertEqual(len(lines), 2)

    def test_range_excludes_out_of_range(self):
        self._login()
        Transaction.objects.create(
            tx_type=Transaction.TxType.SALE, amount=100)
        resp = self.client.get(self.url, {
            'type': 'transactions',
            'start': '2999-01-01', 'end': '2999-01-31',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.content.decode().strip().splitlines()), 1)

    def test_daily_export_with_range(self):
        self._login()
        Transaction.objects.create(
            tx_type=Transaction.TxType.SALE, amount=100)
        today = str(date.today())
        resp = self.client.get(self.url, {
            'type': 'daily', 'start': today, 'end': today,
        })
        self.assertEqual(resp.status_code, 200)
        lines = resp.content.decode().strip().splitlines()
        self.assertEqual(lines[0], 'Date,Total')
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith(today))

    def test_monthly_export_all(self):
        self._login()
        Transaction.objects.create(
            tx_type=Transaction.TxType.SALE, amount=100)
        resp = self.client.get(self.url, {'type': 'monthly'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'monthly_revenue_all.csv', resp['Content-Disposition'])
        lines = resp.content.decode().strip().splitlines()
        self.assertEqual(lines[0], 'Month,Total')
        self.assertEqual(len(lines), 2)
        self.assertIn(date.today().strftime('%Y-%m'), lines[1])


class DashboardViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='pass12345',
            first_name='Admin', last_name='One',
        )
        self.admin.role = User.Role.ADMIN
        self.admin.save()
        self.client.login(email='admin@example.com', password='pass12345')

        self.court = Court.objects.create(name='Court 1', is_active=True)
        self.today = date.today()
        self.noon = timezone.make_aware(
            datetime.combine(self.today, time(12, 0))
        )

    def _booking(self, start, end, status):
        return Booking.objects.create(
            user=self.admin,
            court=self.court,
            date=self.today,
            start_time=start,
            end_time=end,
            status=status,
            price=100,
        )

    def _dashboard(self):
        with patch('dashboard.views.timezone.now', return_value=self.noon), \
             patch('dashboard.views.timezone.localtime', return_value=self.noon):
            return self.client.get(reverse('dashboard:index'))

    def test_booking_counts_include_pending(self):
        self._booking(time(9, 0), time(10, 0), Booking.Status.COMPLETED)
        self._booking(time(13, 0), time(14, 0), Booking.Status.CONFIRMED)
        self._booking(time(15, 0), time(16, 0), Booking.Status.PENDING)

        context = self._dashboard().context
        self.assertEqual(context['bookings_today'], 3)
        self.assertEqual(context['bookings_completed_today'], 1)
        self.assertEqual(context['bookings_pending_today'], 1)

    def test_upcoming_bookings_exclude_ended(self):
        self._booking(time(9, 0), time(10, 0), Booking.Status.COMPLETED)
        self._booking(time(11, 0), time(12, 30), Booking.Status.CONFIRMED)
        self._booking(time(13, 0), time(14, 0), Booking.Status.CONFIRMED)
        self._booking(time(15, 0), time(16, 0), Booking.Status.PENDING)

        upcoming = list(self._dashboard().context['todays_bookings'])
        self.assertEqual(len(upcoming), 3)
        self.assertNotIn(
            time(9, 0), [booking.start_time for booking in upcoming]
        )

    def test_month_change_uses_previous_month(self):
        current = Transaction.objects.create(
            tx_type=Transaction.TxType.SALE,
            amount=300,
            payment_status=Transaction.PaymentStatus.PAID,
        )
        previous = Transaction.objects.create(
            tx_type=Transaction.TxType.SALE,
            amount=200,
            payment_status=Transaction.PaymentStatus.PAID,
        )
        prev_month_end = self.today.replace(day=1) - timedelta(days=1)
        Transaction.objects.filter(pk=previous.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(prev_month_end, time(12, 0))
            )
        )

        context = self._dashboard().context
        self.assertEqual(context['month_revenue'], current.amount)
        self.assertEqual(context['month_change_pct'], 50.0)
        self.assertTrue(context['month_change_up'])
        self.assertEqual(
            context['prev_month_label'], prev_month_end.strftime('%b')
        )

    def test_month_change_is_none_without_previous_data(self):
        Transaction.objects.create(
            tx_type=Transaction.TxType.SALE,
            amount=300,
            payment_status=Transaction.PaymentStatus.PAID,
        )
        self.assertIsNone(self._dashboard().context['month_change_pct'])

    def test_format_duration(self):
        self.assertEqual(
            _format_duration(timedelta(hours=2, minutes=15)), '2h 15m'
        )
        self.assertEqual(
            _format_duration(timedelta(days=3, hours=4)), '3d 4h'
        )
        self.assertEqual(_format_duration(timedelta(minutes=45)), '45m')
