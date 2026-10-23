from datetime import date, time, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from courts.models import Court
from bookings.models import Booking
from bookings.services import (
    create_booking,
    cancel_booking,
    is_slot_available,
    auto_update_booking_statuses,
)

User = get_user_model()


class BookingServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
        )
        self.staff = User.objects.create_user(
            email='staff@test.com',
            password='testpass123',
            first_name='Staff',
            last_name='User',
            role='staff',
            is_staff=True,
        )
        self.court = Court.objects.create(
            name='Court 1',
            is_active=True,
        )
        self.today      = date.today()
        self.tomorrow   = self.today + timedelta(days=1)
        self.slot_9am   = time(9, 0)
        self.slot_10am  = time(10, 0)

    # ── Availability ──────────────────────────────────────────

    def test_slot_is_available_when_no_bookings(self):
        self.assertTrue(
            is_slot_available(self.court, self.tomorrow, self.slot_9am)
        )

    def test_slot_unavailable_after_booking(self):
        create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        self.assertFalse(
            is_slot_available(self.court, self.tomorrow, self.slot_9am)
        )

    def test_different_slot_still_available(self):
        create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        self.assertTrue(
            is_slot_available(self.court, self.tomorrow, self.slot_10am)
        )

    def test_different_court_same_slot_available(self):
        court2 = Court.objects.create(name='Court 2', is_active=True)
        create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        self.assertTrue(
            is_slot_available(court2, self.tomorrow, self.slot_9am)
        )

    # ── Booking Creation ──────────────────────────────────────

    def test_booking_created_with_confirmed_status_onsite(self):
        """Default (onsite) bookings are CONFIRMED."""
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_booking_created_with_pending_status_online(self):
        """Online bookings are PENDING until payment."""
        from django.test import override_settings
        with override_settings(PAYMONGO_SECRET_KEY='sk_test_123', PAYMENTS_ENABLED=True, SITE_URL='https://example.com'):
            booking = create_booking(
                user=self.user,
                court=self.court,
                selected_date=self.tomorrow,
                start_time=self.slot_9am,
                payment_method='online',
            )
            self.assertEqual(booking.status, Booking.Status.PENDING)
            from transactions.models import Transaction
            tx = booking.transaction
            self.assertEqual(tx.provider, Transaction.Provider.PAYMONGO)

    def test_booking_end_time_auto_set(self):
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        self.assertEqual(booking.end_time, self.slot_10am)

    def test_duplicate_booking_raises_error(self):
        create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        with self.assertRaises(ValidationError):
            create_booking(
                user=self.user,
                court=self.court,
                selected_date=self.tomorrow,
                start_time=self.slot_9am,
            )

    def test_past_slot_raises_error(self):
        yesterday = self.today - timedelta(days=1)
        with self.assertRaises(ValidationError):
            create_booking(
                user=self.user,
                court=self.court,
                selected_date=yesterday,
                start_time=self.slot_9am,
            )

    def test_transaction_created_on_booking(self):
        from transactions.models import Transaction
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        self.assertTrue(
            Transaction.objects.filter(booking=booking).exists()
        )

    def test_transaction_is_pending_on_booking(self):
        from transactions.models import Transaction
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        tx = Transaction.objects.get(booking=booking)
        # Transactions start PENDING so the user can pay online (GCash);
        # unpaid pending bookings are marked WAIVED on auto-cancel.
        self.assertEqual(
            tx.payment_status,
            Transaction.PaymentStatus.PENDING
        )

    # ── Cancellation ──────────────────────────────────────────

    def test_cancel_future_confirmed_booking(self):
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        booking.status = Booking.Status.CONFIRMED
        booking.save()
        cancelled = cancel_booking(booking)
        self.assertEqual(cancelled.status, Booking.Status.CANCELLED)

    def test_cancel_raises_error_for_past_booking(self):
        booking = Booking.objects.create(
            user=self.user,
            court=self.court,
            date=self.today - timedelta(days=1),
            start_time=self.slot_9am,
            end_time=self.slot_10am,
            status=Booking.Status.CONFIRMED,
        )
        with self.assertRaises(ValidationError):
            cancel_booking(booking)

    def test_slot_freed_after_cancellation(self):
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
        )
        booking.status = Booking.Status.CONFIRMED
        booking.save()
        cancel_booking(booking)
        self.assertTrue(
            is_slot_available(self.court, self.tomorrow, self.slot_9am)
        )

    # ── Auto Status Update ────────────────────────────────────

    def test_past_confirmed_booking_becomes_completed(self):
        from django.utils import timezone
        yesterday = self.today - timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            court=self.court,
            date=yesterday,
            start_time=time(8, 0),
            end_time=time(9, 0),
            status=Booking.Status.CONFIRMED,
        )
        auto_update_booking_statuses()
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)

    def test_past_pending_booking_becomes_cancelled(self):
        from transactions.models import Transaction
        yesterday = self.today - timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            court=self.court,
            date=yesterday,
            start_time=time(8, 0),
            end_time=time(9, 0),
            status=Booking.Status.PENDING,
        )
        tx = Transaction.objects.create(
            user=self.user,
            tx_type=Transaction.TxType.BOOKING,
            amount=300,
            booking=booking,
        )
        auto_update_booking_statuses()
        booking.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.WAIVED)

    def test_cancel_future_pending_booking(self):
        """PENDING future bookings should now be cancellable (regression fix)."""
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=self.slot_9am,
            payment_method='onsite',
        )
        # Force to PENDING to simulate online reservation
        booking.status = Booking.Status.PENDING
        booking.save(update_fields=['status'])
        self.assertTrue(booking.is_cancellable)
        cancelled = cancel_booking(booking)
        self.assertEqual(cancelled.status, Booking.Status.CANCELLED)

    # ── Price Bracket Tests ────────────────────────────────────

    def test_booking_price_uses_bracket(self):
        """Morning slot should use ₱300 bracket."""
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=time(9, 0),   # 9 AM → ₱300
        )
        self.assertEqual(booking.price, 300)

    def test_booking_price_afternoon_bracket(self):
        """Afternoon slot should use ₱350 bracket."""
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=time(13, 0),  # 1 PM → ₱350
        )
        self.assertEqual(booking.price, 350)

    def test_booking_price_evening_bracket(self):
        """Evening slot should use ₱400 bracket."""
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=time(18, 0),  # 6 PM → ₱400
        )
        self.assertEqual(booking.price, 400)

    def test_booking_price_cross_bracket(self):
        """11 AM slot crosses into afternoon: 300 + 350 = 650...
        but since slots are 1hr, 11-12 = ₱300 entirely."""
        booking = create_booking(
            user=self.user,
            court=self.court,
            selected_date=self.tomorrow,
            start_time=time(11, 0),  # 11 AM → entirely in morning → ₱300
        )
        self.assertEqual(booking.price, 300)