from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from transactions.models import Transaction


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
            'ID,Date,Type,Amount,Payment Status,Description,Created By')
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
