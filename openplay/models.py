from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class OpenPlaySession(models.Model):

    class Status(models.TextChoices):
        OPEN      = 'open',      'Open'
        FULL      = 'full',      'Full'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    title       = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    date        = models.DateField()
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    capacity    = models.PositiveIntegerField(default=10)
    fee         = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status      = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='openplay_sessions_created'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-start_time']
        indexes  = [models.Index(fields=['date', 'status'])]

    def __str__(self):
        return f'{self.title} – {self.date} {self.start_time}'

    @property
    def spots_remaining(self):
        return self.capacity - self.participants.filter(
            status=OpenPlayParticipant.Status.APPROVED
        ).count()

    @property
    def is_full(self):
        return self.spots_remaining <= 0

    def update_status(self):
        """Auto-update session status based on capacity."""
        if self.status not in (self.Status.CANCELLED, self.Status.COMPLETED):
            self.status = self.Status.FULL if self.is_full else self.Status.OPEN
            self.save(update_fields=['status'])


class OpenPlayParticipant(models.Model):

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        REMOVED  = 'removed',  'Removed'

    session = models.ForeignKey(
        OpenPlaySession,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='openplay_participations',
        null=True,   blank=True   # ← nullable for walk-ins
    )
    participant_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Used for walk-in participants without an account.'
    )
    status    = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    joined_at  = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes      = models.TextField(blank=True)

    class Meta:
        # Prevent the same registered user joining same session twice.
        # Walk-ins (user=None) are exempt from this constraint.
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_session_registered_user'
            )
        ]
        indexes = [models.Index(fields=['session', 'status'])]

    def __str__(self):
        return f'{self.display_name} → {self.session} [{self.status}]'

    @property
    def display_name(self):
        """Returns the best available name for this participant."""
        if self.user:
            return self.user.full_name
        return self.participant_name or 'Walk-in Guest'

    def clean(self):
        """Prevent joining a full or closed session."""
        if self.pk:
            return
        if self.session.status == OpenPlaySession.Status.CANCELLED:
            raise ValidationError('This session has been cancelled.')
        if (
            self.session.is_full
            and self.status == self.Status.APPROVED
        ):
            raise ValidationError('This session is full.')