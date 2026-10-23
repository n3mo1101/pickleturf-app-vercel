from datetime import date, time, datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from courts.models import Court
from .models import Booking


# ── Slot Generation ────────────────────────────────────────────────────────────

def get_time_slots():
    """Return list of time slot tuples (time obj, display string)."""
    slots = []
    hour = settings.BOOKING_OPENING_HOUR
    while hour < settings.BOOKING_CLOSING_HOUR:
        t = time(hour, 0)
        end = time(hour + 1, 0)
        label = f'{t.strftime("%I:%M %p")} – {end.strftime("%I:%M %p")}'
        slots.append((t, label))
        hour += 1
    return slots


# ── Availability ───────────────────────────────────────────────────────────────

def get_availability(selected_date):
    """
    Returns dict: { time_slot: { 'courts': {...}, 'price': ..., 'past': bool } }
    with per-court status 'available' | 'booked' | 'past'.
    Used to render the booking grid.
    """
    from datetime import datetime, timedelta
    courts = Court.objects.filter(is_active=True)
    slots  = get_time_slots()

    bookings = Booking.objects.filter(
        date=selected_date,
        status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED]
    ).values('court_id', 'start_time')

    booked_set = {(b['court_id'], b['start_time']) for b in bookings}

    grid = {}
    for slot_time, slot_label in slots:
        slot_price = get_price_for_display(slot_time)
        slot_past  = is_past_slot(selected_date, slot_time)
        grid[slot_label] = {
            'courts': {},
            'price':  slot_price,
            'past':   slot_past,
        }
        for court in courts:
            if slot_past:
                status = 'past'
            elif (court.id, slot_time) in booked_set:
                status = 'booked'
            else:
                status = 'available'
            grid[slot_label]['courts'][court] = status

    return grid


def is_slot_available(court, selected_date, start_time):
    """Check if a specific court/date/time is free."""
    return not Booking.objects.filter(
        court=court,
        date=selected_date,
        start_time=start_time,
        status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED]
    ).exists()


def is_past_slot(selected_date, start_time):
    """Return True if the slot is in the past."""
    slot_dt = datetime.combine(selected_date, start_time)
    slot_dt = timezone.make_aware(slot_dt)
    return slot_dt <= timezone.now()


# ── Booking Creation ───────────────────────────────────────────────────────────

def create_booking(user, court, selected_date, start_time, created_by=None, notes='', payment_method='onsite'):
    """
    Create a booking after validating availability.
    payment_method: 'onsite' (default) → CONFIRMED, 'online' → PENDING until PayMongo webhook.
    Raises ValidationError on conflict.
    """
    if is_past_slot(selected_date, start_time):
        raise ValidationError('Cannot book a slot in the past.')

    if not is_slot_available(court, selected_date, start_time):
        raise ValidationError(
            f'{court.name} is already booked on '
            f'{selected_date.strftime("%b %d")} at '
            f'{start_time.strftime("%I:%M %p")}.'
        )

    # Auto-calculate price based on time bracket
    price = calculate_slot_price(start_time)

    # Decide status/provider based on payment method
    from transactions.payments import payments_enabled
    is_online = (payment_method == 'online' and payments_enabled())

    booking = Booking.objects.create(
        user=user,
        court=court,
        date=selected_date,
        start_time=start_time,
        price=price,
        status=Booking.Status.PENDING if is_online else Booking.Status.CONFIRMED,
        created_by=created_by or user,
        notes=notes,
    )

    _create_booking_transaction(
        booking,
        provider='paymongo' if is_online else 'onsite',
    )
    return booking


def _create_booking_transaction(booking, provider='onsite'):
    """
    Auto-create a pending transaction when a booking is made.
    It only counts toward revenue once paid (online or on-site).
    """
    from transactions.models import Transaction
    provider_value = (
        Transaction.Provider.PAYMONGO if provider == 'paymongo'
        else Transaction.Provider.ONSITE
    )
    Transaction.objects.create(
        user=booking.user,
        tx_type=Transaction.TxType.BOOKING,
        amount=booking.price,
        booking=booking,
        payment_status=Transaction.PaymentStatus.PENDING,
        provider=provider_value,
        description=f'{booking.court} on {booking.date} at {booking.start_time}',
        created_by=booking.created_by,
    )


# ── Cancellation ───────────────────────────────────────────────────────────────

def cancel_booking(booking, cancelled_by=None):
    """
    Cancel a booking if it's still cancellable.
    Raises ValidationError if not allowed.
    """
    if not booking.is_cancellable:
        raise ValidationError('This booking cannot be cancelled.')

    booking.cancel()

    # Mark linked transaction as refunded
    if hasattr(booking, 'transaction'):
        booking.transaction.payment_status = 'refunded'
        booking.transaction.save(update_fields=['payment_status'])

    return booking


# ── Court Availability ───────────────────────────────────────────────────────────────

def get_available_slots_for_court(court, selected_date):
    """Returns list of (value, label, price) for available slots."""
    all_slots = get_time_slots()

    booked_times = set(
        Booking.objects.filter(
            court=court,
            date=selected_date,
            status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED]
        ).values_list('start_time', flat=True)
    )

    available = []
    for slot_time, label in all_slots:
        if slot_time in booked_times:
            continue
        if is_past_slot(selected_date, slot_time):
            continue
        price = get_price_for_display(slot_time)
        available.append((
            slot_time.strftime('%H:%M:%S'),
            label,
        ))

    return available


# ── Automatic Booking Status Update ───────────────────────────────────────────────────────────────

def auto_update_booking_statuses():
    """
    Run on relevant page loads to keep booking statuses current.

    Rules:
      - CONFIRMED + time passed → COMPLETED, transaction → PAID
      - PENDING   + time passed → CANCELLED, transaction stays WAIVED
    """
    from transactions.models import Transaction

    now = timezone.now()

    stale = Booking.objects.filter(
        status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING]
    ).select_related('court')

    for booking in stale:
        if not booking.end_time:
            continue

        end_dt = datetime.combine(booking.date, booking.end_time)
        end_dt = timezone.make_aware(end_dt)

        if end_dt > now:
            continue   # still in the future

        if booking.status == Booking.Status.CONFIRMED:
            booking.status = Booking.Status.COMPLETED
            booking.save(update_fields=['status'])

            # Mark transaction as paid
            try:
                booking.transaction.payment_status = (
                    Transaction.PaymentStatus.PAID
                )
                booking.transaction.save(update_fields=['payment_status'])
            except Exception:
                pass

        elif booking.status == Booking.Status.PENDING:
            booking.status       = Booking.Status.CANCELLED
            booking.cancelled_at = now
            booking.save(update_fields=['status', 'cancelled_at'])
            # Unpaid expired booking — waive the charge (no revenue).
            try:
                tx = booking.transaction
                if tx and tx.payment_status != Transaction.PaymentStatus.PAID:
                    tx.payment_status = Transaction.PaymentStatus.WAIVED
                    tx.save(update_fields=['payment_status'])
            except Exception:
                pass


#── Pricing Calculation ───────────────────────────────────────────────────────────────
    
def calculate_slot_price(start_time, end_time=None):
    """
    Calculate price for a booking slot, handling cross-bracket slots.

    Settings Config:
      08:00 → 12:00  = ₱300  (entirely in morning bracket)
      12:00 → 05:00  = ₱350  (entirely in afternoon bracket)
      05:00 → 1:00  = ₱400  (entirely in evening bracket)
    """
    brackets = settings.BOOKING_PRICE_BRACKETS

    # Auto-set end_time to start + 1 hour if not provided
    if end_time is None:
        dummy_date = datetime(2000, 1, 1)
        start_dt   = datetime.combine(dummy_date, start_time)
        end_dt     = start_dt + timedelta(hours=settings.BOOKING_SLOT_HOURS)
        end_time   = end_dt.time()

    # Convert to minutes since midnight for easier math
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes   = end_time.hour   * 60 + end_time.minute

    total_price = 0

    for bracket_start, bracket_end, rate in brackets:
        b_start = bracket_start * 60
        b_end   = bracket_end   * 60

        # Find overlap between slot and this bracket
        overlap_start = max(start_minutes, b_start)
        overlap_end   = min(end_minutes,   b_end)

        if overlap_end > overlap_start:
            overlap_hours = (overlap_end - overlap_start) / 60
            total_price  += overlap_hours * rate

    return int(total_price)


def get_price_for_display(start_time):
    """Return the price for a single 1-hour slot starting at start_time."""
    from datetime import datetime, timedelta
    dummy = datetime(2000, 1, 1)
    end_time = (datetime.combine(dummy, start_time) + timedelta(hours=1)).time()
    return calculate_slot_price(start_time, end_time)


def get_price_brackets_display():
    """Return human-readable price bracket list for templates."""
    from django.conf import settings
    result = []
    for start_h, end_h, rate in settings.BOOKING_PRICE_BRACKETS:
        from datetime import time
        start_str = time(start_h, 0).strftime('%I:%M %p').lstrip('0')
        end_str   = time(end_h,   0).strftime('%I:%M %p').lstrip('0')
        result.append({
            'label': f'{start_str} – {end_str}',
            'rate':   rate,
        })
    return result
