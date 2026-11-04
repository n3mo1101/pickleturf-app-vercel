from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from courts.models import Court


def _format_time(value):
    """Format a time for compact display, e.g. 9:00 AM."""
    return value.strftime('%I:%M %p').lstrip('0')


def _is_consecutive(slots):
    """True when every slot continues directly from the previous one."""
    return all(
        slots[i - 1].end_time == slots[i].start_time
        for i in range(1, len(slots))
    )


def _first_run_end(slots):
    """End time of the first contiguous run of slots."""
    end_time = slots[0].end_time
    for slot in slots[1:]:
        if slot.start_time != end_time:
            break
        end_time = slot.end_time
    return end_time


class Booking(models.Model):
    """A reservation header covering one or more hourly court slots."""

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    # ── Relationships ──────────────────────────────────────────────
    user  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    court = models.ForeignKey(
        Court,
        on_delete=models.PROTECT,
        related_name='bookings'
    )

    # ── Reservation fields ─────────────────────────────────────────
    date = models.DateField()
    # Summary values derived from BookingSlot rows. They keep ordering,
    # templates, and status transitions simple.
    start_time = models.TimeField()
    end_time   = models.TimeField()

    # ── Booking meta ───────────────────────────────────────────────
    status     = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    price      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes      = models.TextField(blank=True)

    # ── Audit ──────────────────────────────────────────────────────
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bookings_created'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['date', 'court']),
            models.Index(fields=['user', 'date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return (
            f'{self.court} | {self.date} {self.start_time} | {self.user}'
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Prevent changing the court/date out from under existing slots."""
        if not self.pk or not self.slots.exists():
            return
        original = (
            Booking.objects
            .filter(pk=self.pk)
            .values('court_id', 'date')
            .first()
        )
        if original and (
            original['court_id'] != self.court_id
            or original['date'] != self.date
        ):
            raise ValidationError(
                'Court and date cannot be changed after slots are created. '
                'Cancel and rebook instead.'
            )

    # ── Slot helpers ───────────────────────────────────────────────

    @property
    def slot_count(self):
        return self.slots.count()

    @property
    def is_consecutive(self):
        """True when every slot continues directly from the previous one."""
        return _is_consecutive(list(self.slots.all()))

    @property
    def first_time_range(self):
        """First contiguous run, used for the compact table summary."""
        slots = list(self.slots.all())
        if not slots:
            return f'{_format_time(self.start_time)} – {_format_time(self.end_time)}'

        return (
            f'{_format_time(slots[0].start_time)} – '
            f'{_format_time(_first_run_end(slots))}'
        )

    @property
    def time_summary(self):
        """Full summary used in descriptions and confirmations."""
        slots = list(self.slots.all())
        if not slots:
            return f'{_format_time(self.start_time)} – {_format_time(self.end_time)}'
        if _is_consecutive(slots):
            return (
                f'{_format_time(slots[0].start_time)} – '
                f'{_format_time(slots[-1].end_time)}'
            )

        shown = ', '.join(
            f'{_format_time(s.start_time)}–{_format_time(s.end_time)}'
            for s in slots[:2]
        )
        remaining = len(slots) - 2
        return shown + (f' +{remaining} more' if remaining else '')

    def sync_summary_from_slots(self):
        """Recompute the denormalized summary fields from child slots."""
        slots = list(self.slots.order_by('start_time'))
        if not slots:
            return
        self.start_time = slots[0].start_time
        self.end_time = max(slot.end_time for slot in slots)
        self.price = sum((slot.price for slot in slots), 0)
        self.save(update_fields=['start_time', 'end_time', 'price', 'updated_at'])

    def cancel(self, save=True):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'cancelled_at', 'updated_at'])
            self.slots.update(is_active=False)

    @property
    def is_cancellable(self):
        """Allow cancellation if pending or confirmed and still in the future."""
        booking_dt = datetime.combine(self.date, self.start_time)
        booking_dt = timezone.make_aware(booking_dt)
        return (
            self.status in (self.Status.PENDING, self.Status.CONFIRMED)
            and booking_dt > timezone.now()
        )


class BookingSlot(models.Model):
    """A single hourly court slot belonging to a Booking reservation."""

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='slots',
    )
    # court/date are denormalized so the partial unique constraint can
    # enforce availability without joining the parent booking.
    court = models.ForeignKey(
        Court,
        on_delete=models.PROTECT,
        related_name='booking_slots',
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['start_time']
        indexes = [
            models.Index(
                fields=['date', 'court', 'is_active'],
                name='bslot_date_court_active_idx',
            ),
            models.Index(
                fields=['booking', 'start_time'],
                name='bslot_booking_start_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['court', 'date', 'start_time'],
                condition=models.Q(is_active=True),
                name='unique_active_booking_slot',
            )
        ]

    def __str__(self):
        return (
            f'{self.court} | {self.date} '
            f'{self.start_time}–{self.end_time}'
        )

    def save(self, *args, **kwargs):
        if self.booking_id:
            if not self.court_id:
                self.court_id = self.booking.court_id
            if not self.date:
                self.date = self.booking.date
        if self.date and self.start_time:
            dt = datetime.combine(self.date, self.start_time)
            self.end_time = (
                dt + timedelta(hours=settings.BOOKING_SLOT_HOURS)
            ).time()
        super().save(*args, **kwargs)

    def clean(self):
        if self.booking_id:
            if self.court_id and self.court_id != self.booking.court_id:
                raise ValidationError('Slot court must match the booking court.')
            if self.date and self.date != self.booking.date:
                raise ValidationError('Slot date must match the booking date.')
