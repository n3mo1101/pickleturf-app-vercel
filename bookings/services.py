from datetime import date, time, datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from courts.models import Court
from .models import Booking, BookingSlot


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
    courts = Court.objects.filter(is_active=True)
    slots  = get_time_slots()

    booked_slots = BookingSlot.objects.filter(
        date=selected_date,
        is_active=True,
        booking__status=Booking.Status.RESERVED,
    ).values('court_id', 'start_time')

    booked_set = {(s['court_id'], s['start_time']) for s in booked_slots}

    grid = {}
    for slot_time, slot_label in slots:
        slot_price = get_price_for_display(slot_time)
        slot_past  = is_past_slot(selected_date, slot_time)
        grid[slot_label] = {
            'courts': {},
            'price':  slot_price,
            'past':   slot_past,
            'time':   slot_time.strftime('%H:%M:%S'),
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
    return not BookingSlot.objects.filter(
        court=court,
        date=selected_date,
        start_time=start_time,
        is_active=True,
        booking__status=Booking.Status.RESERVED,
    ).exists()


def is_past_slot(selected_date, start_time):
    """Return True if the slot is in the past."""
    slot_dt = datetime.combine(selected_date, start_time)
    slot_dt = timezone.make_aware(slot_dt)
    return slot_dt <= timezone.now()


# ── Booking Creation ───────────────────────────────────────────────────────────

def _slot_end(start_time):
    dummy = datetime(2000, 1, 1)
    return (
        datetime.combine(dummy, start_time)
        + timedelta(hours=settings.BOOKING_SLOT_HOURS)
    ).time()


def _coerce_time(value):
    if isinstance(value, time):
        return value
    return datetime.strptime(str(value), '%H:%M:%S').time()


def create_booking(
    user,
    court,
    selected_date,
    start_times=None,
    created_by=None,
    notes='',
    payment_method='onsite',
    start_time=None,
    mark_paid=False,
):
    """
    Create a reservation covering one or more time slots atomically.

    Every reservation starts as RESERVED — the slot is held immediately.
    payment_method only decides the transaction provider ('onsite' or
    'paymongo'); mark_paid settles it on the spot (counter payment).
    Raises ValidationError on any conflict.
    """
    if start_times is None:
        start_times = [start_time] if start_time is not None else []

    times = sorted({_coerce_time(value) for value in start_times})
    if not times:
        raise ValidationError('Please select at least one slot.')

    # Validate every slot before creating anything.
    for slot_time in times:
        if is_past_slot(selected_date, slot_time):
            raise ValidationError('Cannot book a slot in the past.')
        if not is_slot_available(court, selected_date, slot_time):
            raise ValidationError(
                f'{court.name} is already booked on '
                f'{selected_date.strftime("%b %d")} at '
                f'{slot_time.strftime("%I:%M %p")}.'
            )

    prices = {slot_time: calculate_slot_price(slot_time) for slot_time in times}
    total_price = sum(prices.values())

    from transactions.payments import payments_enabled
    is_online = (payment_method == 'online' and payments_enabled())

    summary_start = times[0]
    summary_end = max(_slot_end(slot_time) for slot_time in times)

    try:
        with transaction.atomic():
            booking = Booking.objects.create(
                user=user,
                court=court,
                date=selected_date,
                start_time=summary_start,
                end_time=summary_end,
                price=total_price,
                status=Booking.Status.RESERVED,
                created_by=created_by or user,
                notes=notes,
            )

            for slot_time in times:
                BookingSlot.objects.create(
                    booking=booking,
                    court=court,
                    date=selected_date,
                    start_time=slot_time,
                    price=prices[slot_time],
                )

            _create_booking_transaction(
                booking,
                provider='paymongo' if is_online else 'onsite',
                paid=mark_paid,
            )
    except IntegrityError as exc:
        raise ValidationError(
            'One or more selected slots were just booked. '
            'Please choose different slots.'
        ) from exc

    return booking


def _create_booking_transaction(booking, provider='onsite', paid=False):
    """
    Create the single transaction for a reservation.

    It only counts toward revenue once paid (online or on-site). When
    `paid` is true the charge is settled immediately (counter payment).
    """
    from transactions.models import Transaction
    from django.utils import timezone

    provider_value = (
        Transaction.Provider.PAYMONGO if provider == 'paymongo'
        else Transaction.Provider.ONSITE
    )
    Transaction.objects.create(
        user=booking.user,
        tx_type=Transaction.TxType.BOOKING,
        amount=booking.price,
        booking=booking,
        payment_status=(
            Transaction.PaymentStatus.PAID if paid
            else Transaction.PaymentStatus.PENDING
        ),
        paid_at=timezone.now() if paid else None,
        provider=provider_value,
        description=(
            f'{booking.court} on {booking.date} '
            f'({booking.slot_count} slot(s), {booking.time_summary})'
        ),
        created_by=booking.created_by,
    )


# ── Cancellation ───────────────────────────────────────────────────────────────

def cancel_booking(booking, cancelled_by=None):
    """
    Cancel a reservation if it's still cancellable.
    Raises ValidationError if not allowed.
    """
    if not booking.is_cancellable:
        raise ValidationError('This booking cannot be cancelled.')

    from transactions.models import Transaction

    with transaction.atomic():
        booking.cancel()

        try:
            tx = booking.transaction
        except Transaction.DoesNotExist:
            tx = None
        if tx:
            tx.payment_status = (
                Transaction.PaymentStatus.REFUNDED
                if tx.payment_status == Transaction.PaymentStatus.PAID
                else Transaction.PaymentStatus.WAIVED
            )
            tx.save(update_fields=['payment_status', 'updated_at'])

    return booking


# ── Status Changes ─────────────────────────────────────────────────────────────

def _sync_transaction_status(booking, new_status):
    """Keep the single linked transaction in step with the booking.

    Only cancellation affects payment: a collected charge becomes
    refunded, anything else is written off. Completion never marks a
    booking paid — that is recorded separately (staff / PayMongo).
    """
    from transactions.models import Transaction

    if new_status != Booking.Status.CANCELLED:
        return

    try:
        tx = booking.transaction
    except Transaction.DoesNotExist:
        return

    tx.payment_status = (
        Transaction.PaymentStatus.REFUNDED
        if tx.payment_status == Transaction.PaymentStatus.PAID
        else Transaction.PaymentStatus.WAIVED
    )
    tx.save(update_fields=['payment_status', 'updated_at'])


def set_booking_status(booking, new_status):
    """
    Update a booking's status, keeping slot availability and the linked
    transaction consistent. Used by the admin status view.
    """
    if new_status == Booking.Status.MISSED:
        raise ValidationError(
            'Missed is set automatically when a slot passes unpaid.'
        )
    if new_status not in dict(Booking.EDITABLE_STATUSES):
        raise ValidationError('Invalid status.')

    was_cancelled = booking.status == Booking.Status.CANCELLED

    try:
        with transaction.atomic():
            if new_status == Booking.Status.CANCELLED:
                booking.cancel()
                _sync_transaction_status(booking, new_status)
                return booking

            if was_cancelled:
                # Reactivating a cancelled reservation must not steal slots.
                conflicts = []
                for slot in booking.slots.all():
                    if not is_slot_available(
                        slot.court, slot.date, slot.start_time
                    ):
                        conflicts.append(slot)
                if conflicts:
                    slot = conflicts[0]
                    raise ValidationError(
                        f'Cannot reactivate: {slot.court} is already booked '
                        f'on {slot.date.strftime("%b %d")} at '
                        f'{slot.start_time.strftime("%I:%M %p")}.'
                    )
                booking.slots.update(is_active=True)
                booking.cancelled_at = None

            booking.status = new_status
            booking.save(update_fields=['status', 'cancelled_at', 'updated_at'])
            _sync_transaction_status(booking, new_status)

            if was_cancelled:
                # A cancelled checkout session is stale; force a fresh one.
                from transactions.models import Transaction
                try:
                    tx = booking.transaction
                except Transaction.DoesNotExist:
                    tx = None
                if tx and tx.provider_checkout_id:
                    tx.provider_checkout_id = ''
                    tx.save(
                        update_fields=['provider_checkout_id', 'updated_at']
                    )
    except IntegrityError as exc:
        raise ValidationError(
            'One or more slots were just booked. Please try again.'
        ) from exc

    return booking


# ── Court Availability ─────────────────────────────────────────────────────────

def get_available_slots_for_court(court, selected_date):
    """Returns list of (value, label) for available slots."""
    all_slots = get_time_slots()

    booked_times = set(
        BookingSlot.objects.filter(
            court=court,
            date=selected_date,
            is_active=True,
            booking__status=Booking.Status.RESERVED,
        ).values_list('start_time', flat=True)
    )

    available = []
    for slot_time, label in all_slots:
        if slot_time in booked_times:
            continue
        if is_past_slot(selected_date, slot_time):
            continue
        available.append((
            slot_time.strftime('%H:%M:%S'),
            label,
        ))

    return available


# ── Automatic Booking Status Update ───────────────────────────────────────────

def auto_update_booking_statuses():
    """
    Keep booking statuses current. Called by the daily Vercel Cron endpoint
    (`/bookings/cron/update-statuses/`) and the `update_booking_statuses`
    management command, and opportunistically on page loads.

    Rules (reserved bookings whose last slot has passed):
      - transaction PAID                  → COMPLETED
      - transaction not paid (or missing) → MISSED, unpaid charge waived

    Payment is never forced to PAID here — only actual payment does that.
    """
    from transactions.models import Transaction

    now = timezone.now()

    stale = (
        Booking.objects
        .filter(status=Booking.Status.RESERVED)
        .select_related('court')
        .prefetch_related('slots')
    )

    for booking in stale:
        if not booking.end_time:
            continue

        end_dt = datetime.combine(booking.date, booking.end_time)
        end_dt = timezone.make_aware(end_dt)

        if end_dt > now:
            continue   # still in the future

        try:
            tx = booking.transaction
        except Transaction.DoesNotExist:
            tx = None

        if tx and tx.payment_status == Transaction.PaymentStatus.PAID:
            booking.status = Booking.Status.COMPLETED
            booking.save(update_fields=['status', 'updated_at'])
            continue

        # No payment collected — the slot was missed. Write off the charge
        # so it never counts as revenue.
        booking.status = Booking.Status.MISSED
        booking.save(update_fields=['status', 'updated_at'])

        if tx and tx.payment_status == Transaction.PaymentStatus.PENDING:
            tx.payment_status = Transaction.PaymentStatus.WAIVED
            tx.save(update_fields=['payment_status', 'updated_at'])


# ── Pricing Calculation ───────────────────────────────────────────────────────

def calculate_slot_price(start_time, end_time=None):
    """
    Calculate price for a booking slot, handling cross-bracket slots.

    Settings Config:
      08:00 → 12:00  = ₱300  (entirely in morning bracket)
      12:00 → 05:00  = ₱350  (entirely in afternoon bracket)
      05:00 → 1:00   = ₱400  (entirely in evening bracket)
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
    dummy = datetime(2000, 1, 1)
    end_time = (
        datetime.combine(dummy, start_time)
        + timedelta(hours=settings.BOOKING_SLOT_HOURS)
    ).time()
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
