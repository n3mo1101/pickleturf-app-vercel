"""Tests for the PayMongo online payment feature."""
import hashlib
import hmac
import json
import time
from datetime import date, time as dtime, timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from courts.models import Court
from bookings.models import Booking
from bookings import services as booking_services
from openplay.models import OpenPlaySession, OpenPlayParticipant
from transactions.models import Transaction
from transactions import payments

TEST_KEYS = {
    'PAYMONGO_SECRET_KEY': 'sk_test_abc123',
    'PAYMONGO_PUBLIC_KEY': 'pk_test_abc123',
    'PAYMONGO_WEBHOOK_SECRET': 'whsk_test_abc123',
    'PAYMENTS_ENABLED': True,
    'SITE_URL': 'https://pickleturf.example.com',
}


def sign_payload(payload, secret='whsk_test_abc123'):
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f'{ts}.{payload}'.encode(), hashlib.sha256).hexdigest()
    return f't={ts},te={sig},li='


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='player@example.com', password='pass12345',
            first_name='Test', last_name='Player',
        )
        self.admin = User.objects.create_user(
            email='admin@example.com', password='pass12345',
            first_name='Admin', last_name='One',
        )
        self.admin.role = User.Role.ADMIN
        self.admin.save()
        self.court = Court.objects.create(name='Court A', is_active=True)


class WebhookSignatureTests(BaseTestCase):
    @override_settings(**TEST_KEYS)
    def test_valid_signature_passes(self):
        payload = json.dumps({'data': {}})
        self.assertTrue(payments.verify_webhook_signature(payload, sign_payload(payload)))

    @override_settings(**TEST_KEYS)
    def test_invalid_signature_fails(self):
        payload = json.dumps({'data': {}})
        bad = 't=123,te=deadbeef,li='
        self.assertFalse(payments.verify_webhook_signature(payload, bad))

    @override_settings(**TEST_KEYS)
    def test_missing_header_fails(self):
        self.assertFalse(payments.verify_webhook_signature('{}', ''))

    @override_settings(**TEST_KEYS)
    def test_replayed_timestamp_fails(self):
        payload = json.dumps({'data': {}})
        old_ts = str(int(time.time()) - 3600)
        sig = hmac.new('whsk_test_abc123'.encode(), f'{old_ts}.{payload}'.encode(), hashlib.sha256).hexdigest()
        self.assertFalse(payments.verify_webhook_signature(payload, f't={old_ts},te={sig},li='))

    @override_settings(PAYMONGO_SECRET_KEY='', PAYMENTS_ENABLED=False)
    def test_disabled_payments(self):
        self.assertFalse(payments.payments_enabled())


class BookingPaymentTests(BaseTestCase):
    @override_settings(**TEST_KEYS)
    def test_booking_creates_pending_transaction(self):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(9, 0),
            payment_method='online',
        )
        tx = b.transaction
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PENDING)
        self.assertEqual(tx.amount, b.price)
        self.assertGreater(tx.amount, 0)

    @override_settings(**TEST_KEYS)
    def test_paid_webhook_confirms_booking(self):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(10, 0),
            payment_method='online',
        )
        tx = b.transaction
        payload = json.dumps({
            'data': {
                'type': 'checkout_session.payment.paid',
                'data': {
                    'id': 'cs_0001',
                    'attributes': {
                        'reference_number': str(tx.pk),
                        'payments': [{
                            'id': 'pay_0001',
                            'attributes': {
                                'amount': int(tx.amount * 100),
                                'status': 'paid',
                                'source': {'type': 'gcash'},
                            },
                        }],
                    },
                },
            },
        })
        handled = payments.handle_webhook_payload(json.loads(payload))
        self.assertIsNotNone(handled)
        tx.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PAID)
        self.assertEqual(tx.payment_method, 'gcash')
        self.assertEqual(tx.provider_payment_id, 'pay_0001')
        self.assertIsNotNone(tx.paid_at)
        self.assertEqual(b.status, Booking.Status.CONFIRMED)

    @override_settings(**TEST_KEYS)
    def test_webhook_is_idempotent(self):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(11, 0),
            payment_method='online',
        )
        tx = b.transaction
        payload = json.loads(json.dumps({
            'data': {
                'type': 'checkout_session.payment.paid',
                'data': {
                    'id': 'cs_0002',
                    'attributes': {
                        'reference_number': str(tx.pk),
                        'payments': [{
                            'id': 'pay_0002',
                            'attributes': {
                                'amount': int(tx.amount * 100),
                                'status': 'paid',
                                'source': {'type': 'gcash'},
                            },
                        }],
                    },
                },
            },
        }))
        payments.handle_webhook_payload(payload)
        payments.handle_webhook_payload(payload)  # re-delivery
        self.assertEqual(
            Transaction.objects.filter(provider_payment_id='pay_0002').count(),
            1,
        )
        tx.refresh_from_db()
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PAID)

    @override_settings(**TEST_KEYS)
    def test_amount_mismatch_is_ignored(self):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(12, 0),
            payment_method='online',
        )
        tx = b.transaction
        payload = json.loads(json.dumps({
            'data': {
                'type': 'checkout_session.payment.paid',
                'data': {
                    'id': 'cs_0003',
                    'attributes': {
                        'reference_number': str(tx.pk),
                        'payments': [{
                            'id': 'pay_0003',
                            'attributes': {'amount': 1, 'status': 'paid', 'source': {'type': 'gcash'}},
                        }],
                    },
                },
            },
        }))
        handled = payments.handle_webhook_payload(payload)
        self.assertIsNone(handled)
        tx.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PENDING)
        self.assertEqual(b.status, Booking.Status.PENDING)

    @override_settings(**TEST_KEYS)
    def test_webhook_endpoint_rejects_bad_signature(self):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(13, 0),
            payment_method='online',
        )
        client = Client()
        resp = client.post(
            reverse('transactions:webhook'),
            data='{}',
            content_type='application/json',
            HTTP_PAYMONGO_WEBHOOK_SIGNATURE='t=1,te=bad,li=',
        )
        self.assertEqual(resp.status_code, 403)

    @override_settings(**TEST_KEYS)
    def test_webhook_endpoint_fulfills_payment(self):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(14, 0),
            payment_method='online',
        )
        tx = b.transaction
        payload = json.dumps({
            'data': {
                'type': 'checkout_session.payment.paid',
                'data': {
                    'id': 'cs_0004',
                    'attributes': {
                        'reference_number': str(tx.pk),
                        'payments': [{
                            'id': 'pay_0004',
                            'attributes': {
                                'amount': int(tx.amount * 100),
                                'status': 'paid',
                                'source': {'type': 'gcash'},
                            },
                        }],
                    },
                },
            },
        })
        resp = self.client.post(
            reverse('transactions:webhook'),
            data=payload,
            content_type='application/json',
            HTTP_PAYMONGO_WEBHOOK_SIGNATURE=sign_payload(payload),
        )
        self.assertEqual(resp.status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PAID)


class OpenPlayPaymentTests(BaseTestCase):
    def _session(self, fee=100):
        return OpenPlaySession.objects.create(
            title='Weekend League', date=date.today() + timedelta(days=3),
            start_time=dtime(9, 0), end_time=dtime(11, 0),
            capacity=10, fee=fee, created_by=self.admin,
        )

    @override_settings(**TEST_KEYS)
    def test_join_paid_session_creates_pending_tx(self):
        sess = self._session()
        from openplay import services
        participant = services.request_join(self.user, sess)
        tx = Transaction.objects.get(openplay=participant)
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PENDING)
        self.assertEqual(tx.amount, sess.fee)
        self.assertEqual(tx.provider, Transaction.Provider.PAYMONGO)

    @override_settings(PAYMONGO_SECRET_KEY='', PAYMENTS_ENABLED=False)
    def test_join_paid_session_no_tx_when_payments_disabled(self):
        sess = self._session()
        from openplay import services
        participant = services.request_join(self.user, sess)
        self.assertFalse(Transaction.objects.filter(openplay=participant).exists())

    @override_settings(**TEST_KEYS)
    def test_paid_webhook_approves_participant(self):
        sess = self._session()
        from openplay import services
        participant = services.request_join(self.user, sess)
        tx = Transaction.objects.get(openplay=participant)
        payload = json.loads(json.dumps({
            'data': {
                'type': 'checkout_session.payment.paid',
                'data': {
                    'id': 'cs_0010',
                    'attributes': {
                        'reference_number': str(tx.pk),
                        'payments': [{
                            'id': 'pay_0010',
                            'attributes': {
                                'amount': int(tx.amount * 100),
                                'status': 'paid',
                                'source': {'type': 'gcash'},
                            },
                        }],
                    },
                },
            },
        }))
        payments.handle_webhook_payload(payload)
        participant.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(participant.status, OpenPlayParticipant.Status.APPROVED)
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PAID)

    @override_settings(**TEST_KEYS)
    def test_free_session_keeps_admin_approval_flow(self):
        sess = self._session(fee=0)
        from openplay import services
        participant = services.request_join(self.user, sess)
        self.assertFalse(Transaction.objects.filter(openplay=participant).exists())
        services.approve_participant(participant)
        participant.refresh_from_db()
        self.assertEqual(participant.status, OpenPlayParticipant.Status.APPROVED)


class CheckoutViewTests(BaseTestCase):
    @override_settings(**TEST_KEYS)
    @patch('transactions.payments.requests.post')
    def test_checkout_redirects_to_paymongo(self, mock_post):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(15, 0),
            payment_method='online',
        )
        tx = b.transaction
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'data': {
                'id': 'cs_new_1',
                'attributes': {'checkout_url': 'https://checkout.paymongo.com/x'},
            }
        }
        self.client.login(email='player@example.com', password='pass12345')
        resp = self.client.get(reverse('transactions:pay_online', args=[tx.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, 'https://checkout.paymongo.com/x')
        mock_post.assert_called_once()
        tx.refresh_from_db()
        self.assertEqual(tx.provider_checkout_id, 'cs_new_1')
        self.assertEqual(tx.provider, Transaction.Provider.PAYMONGO)

    @override_settings(**TEST_KEYS)
    @patch('transactions.payments.requests.post')
    def test_checkout_owner_only(self, mock_post):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(16, 0),
            payment_method='online',
        )
        tx = b.transaction
        other = User.objects.create_user(
            email='other@example.com', password='pass12345',
            first_name='Other', last_name='User',
        )
        self.client.login(email='other@example.com', password='pass12345')
        resp = self.client.get(reverse('transactions:pay_online', args=[tx.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('checkout.paymongo.com', resp.url or '')
        mock_post.assert_not_called()

    @override_settings(**TEST_KEYS)
    @patch('transactions.payments.requests.post')
    def test_checkout_reuses_existing_session(self, mock_post):
        b = booking_services.create_booking(
            user=self.user, court=self.court,
            selected_date=date.today() + timedelta(days=1),
            start_time=dtime(17, 0),
            payment_method='online',
        )
        tx = b.transaction
        tx.provider_checkout_id = 'cs_existing'
        tx.save()
        with patch('transactions.payments.requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': {'attributes': {'checkout_url': 'https://checkout.paymongo.com/reused'}}
            }
            self.client.login(email='player@example.com', password='pass12345')
            resp = self.client.get(reverse('transactions:pay_online', args=[tx.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, 'https://checkout.paymongo.com/reused')
        mock_post.assert_not_called()
