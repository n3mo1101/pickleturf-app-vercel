from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from courts.models import Court


class Booking(models.Model):

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

    # ── Slot fields ────────────────────────────────────────────────
    date       = models.DateField()
    start_time = models.TimeField()   # e.g. 09:00
    end_time   = models.TimeField()   # always start + 1 hr

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
        # Prevent exact duplicate bookings at DB level
        constraints = [
            models.UniqueConstraint(
                fields=['court', 'date', 'start_time'],
                condition=models.Q(status__in=['pending', 'confirmed']),
                name='unique_active_court_slot'
            )
        ]

    def __str__(self):
        return f'{self.court} | {self.date} {self.start_time} | {self.user}'

    def clean(self):
        """Validate no overlapping active booking for same court/slot."""
        if not self.date or not self.start_time:
            return
        conflict = Booking.objects.filter(
            court=self.court,
            date=self.date,
            start_time=self.start_time,
            status__in=[self.Status.PENDING, self.Status.CONFIRMED]
        ).exclude(pk=self.pk)

        if conflict.exists():
            raise ValidationError(
                f'Court {self.court} is already booked on '
                f'{self.date} at {self.start_time}.'
            )

    def save(self, *args, **kwargs):
        # Set end_time FIRST, then validate
        from datetime import datetime, timedelta
        if self.date and self.start_time:
            dt = datetime.combine(self.date, self.start_time)
            self.end_time = (dt + timedelta(hours=1)).time()
        self.full_clean()
        super().save(*args, **kwargs)

    def cancel(self, save=True):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        if save:
            self.save()

    @property
    def is_cancellable(self):
        """Allow cancellation if pending or confirmed and still in the future."""
        from datetime import datetime
        booking_dt = datetime.combine(self.date, self.start_time)
        booking_dt = timezone.make_aware(booking_dt)
        return (
            self.status in (self.Status.PENDING, self.Status.CONFIRMED)
            and booking_dt > timezone.now()
        )