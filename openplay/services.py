from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import OpenPlaySession, OpenPlayParticipant


# ── Session Helpers ────────────────────────────────────────────────────────────

def auto_update_session_statuses():
    """
    Mark open play sessions as completed once their end time has passed.

    Mirrors booking auto-updates: only OPEN/FULL sessions are considered,
    and cancelled or already-completed sessions are left untouched.
    Called by the daily cron, page loads, the dashboard, and the customer
    home so stale sessions never stay "upcoming".
    """
    now = timezone.now()
    today = timezone.localdate()

    sessions = OpenPlaySession.objects.filter(
        status__in=[
            OpenPlaySession.Status.OPEN,
            OpenPlaySession.Status.FULL,
        ],
        date__lte=today,
    )

    for session in sessions:
        end_dt = timezone.make_aware(
            datetime.combine(session.date, session.end_time)
        )
        if end_dt > now:
            continue   # still running or in the future

        session.status = OpenPlaySession.Status.COMPLETED
        session.save(update_fields=['status'])


def _ensure_session_accepts_participants(session):
    """Reject approvals/additions once a session is closed or has ended."""
    if session.status == OpenPlaySession.Status.CANCELLED:
        raise ValidationError('This session has been cancelled.')
    if session.status == OpenPlaySession.Status.COMPLETED:
        raise ValidationError('This session has already ended.')


def get_upcoming_sessions():
    """Return all open/upcoming sessions sorted by date."""
    return OpenPlaySession.objects.filter(
        status__in=[OpenPlaySession.Status.OPEN, OpenPlaySession.Status.FULL]
    ).order_by('date', 'start_time')


def get_past_sessions():
    """Return completed/cancelled sessions."""
    return OpenPlaySession.objects.filter(
        status__in=[OpenPlaySession.Status.COMPLETED, OpenPlaySession.Status.CANCELLED]
    ).order_by('-date', '-start_time')


# ── Join / Leave ───────────────────────────────────────────────────────────────

def request_join(user, session):
    """
    User requests to join an open-play session.
    Raises ValidationError if not allowed.
    """
    if session.status == OpenPlaySession.Status.CANCELLED:
        raise ValidationError('This session has been cancelled.')

    if session.status == OpenPlaySession.Status.COMPLETED:
        raise ValidationError('This session has already ended.')

    already = OpenPlayParticipant.objects.filter(
        session=session, user=user
    ).exclude(status=OpenPlayParticipant.Status.REMOVED).exists()

    if already:
        raise ValidationError('You have already joined or requested this session.')

    participant = OpenPlayParticipant.objects.create(
        session=session,
        user=user,
        status=OpenPlayParticipant.Status.PENDING,
    )

    # Pay-to-join: paid sessions generate the transaction up front so the
    # user can pay online (GCash). Webhook approval marks them APPROVED.
    if session.fee > 0:
        from transactions import payments
        from transactions.models import Transaction
        if payments.payments_enabled():
            _create_openplay_transaction(
                participant,
                provider=Transaction.Provider.PAYMONGO,
            )
    return participant


def leave_session(user, session):
    """User withdraws their join request or leaves a session."""
    try:
        participant = OpenPlayParticipant.objects.get(
            session=session,
            user=user,
            status__in=[
                OpenPlayParticipant.Status.PENDING,
                OpenPlayParticipant.Status.APPROVED,
            ]
        )
    except OpenPlayParticipant.DoesNotExist:
        raise ValidationError('You are not a participant of this session.')

    # Free up the spot if they were approved
    was_approved = participant.status == OpenPlayParticipant.Status.APPROVED
    participant.status = OpenPlayParticipant.Status.REMOVED
    participant.save(update_fields=['status'])

    if was_approved:
        session.update_status()

    return participant


# ── Admin Actions ──────────────────────────────────────────────────────────────

def approve_participant(participant):
    """Admin approves a pending join request."""
    _ensure_session_accepts_participants(participant.session)

    if participant.session.is_full:
        raise ValidationError('Session is full. Cannot approve more participants.')

    participant.status = OpenPlayParticipant.Status.APPROVED
    participant.save(update_fields=['status'])
    participant.session.update_status()

    # Approval implies an on-site/cash settlement.
    _settle_openplay_payment(participant)
    return participant


def reject_participant(participant):
    """Admin rejects a pending join request."""
    participant.status = OpenPlayParticipant.Status.REJECTED
    participant.save(update_fields=['status'])
    return participant


def add_participant_manually(admin_user, session, participant_name):
    """
    Admin directly adds a user to a session as approved.
    Adds a walk-in participant by name.
    """
    _ensure_session_accepts_participants(session)

    if session.is_full:
        raise ValidationError('Session is full.')

    participant = OpenPlayParticipant.objects.create(
        session=session,
        user=None,
        participant_name=participant_name.strip(),
        status=OpenPlayParticipant.Status.APPROVED,
    )

    session.update_status()
    _create_openplay_transaction(participant, paid=True)
    return participant


def complete_session(session):
    """Mark session as completed."""
    session.status = OpenPlaySession.Status.COMPLETED
    session.save(update_fields=['status'])
    return session


def cancel_session(session):
    """Cancel a session and mark all approved participants as removed."""
    session.status = OpenPlaySession.Status.CANCELLED
    session.save(update_fields=['status'])
    session.participants.filter(
        status=OpenPlayParticipant.Status.APPROVED
    ).update(status=OpenPlayParticipant.Status.REMOVED)
    return session


def _settle_openplay_payment(participant):
    """
    Settlement for an approved participant.

    An existing online transaction (created when they requested to join)
    is marked paid; otherwise a paid on-site transaction is created.
    Already-paid transactions keep their provider (e.g. PayMongo).
    """
    from transactions.models import Transaction
    from transactions.services import mark_transaction_paid

    tx = (
        Transaction.objects
        .filter(openplay=participant)
        .order_by('-created_at')
        .first()
    )
    if tx:
        if tx.payment_status != Transaction.PaymentStatus.PAID:
            mark_transaction_paid(
                tx, provider=Transaction.Provider.ONSITE
            )
        return tx

    return _create_openplay_transaction(participant, paid=True)


def _create_openplay_transaction(participant, provider=None, paid=False):
    """Create the (single) transaction for an open-play participant."""
    from django.utils import timezone

    from transactions.models import Transaction

    # Avoid duplicate transactions
    if Transaction.objects.filter(openplay=participant).exists():
        return
    if participant.session.fee <= 0:
        return
    Transaction.objects.create(
        user=participant.user,
        tx_type=Transaction.TxType.OPENPLAY,
        amount=participant.session.fee,
        openplay=participant,
        payment_status=(
            Transaction.PaymentStatus.PAID if paid
            else Transaction.PaymentStatus.PENDING
        ),
        paid_at=timezone.now() if paid else None,
        provider=provider or Transaction.Provider.ONSITE,
        description=(
            f'{participant.session.title} '
            f'on {participant.session.date}'
        ),
    )