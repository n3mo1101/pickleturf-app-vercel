from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_or_staff_required
from .forms import AddParticipantForm, OpenPlaySessionForm
from .models import OpenPlayParticipant, OpenPlaySession
from . import services


# ── Customer Views ─────────────────────────────────────────────────────────────

@login_required
def session_list_view(request):
    """Show upcoming open-play sessions to customers."""
    upcoming = services.get_upcoming_sessions()
    past     = services.get_past_sessions()

    # Annotate which sessions the current user has joined
    user_sessions = OpenPlayParticipant.objects.filter(
        user=request.user
    ).exclude(
        status=OpenPlayParticipant.Status.REMOVED
    ).values_list('session_id', 'status')

    user_status_map = {sid: status for sid, status in user_sessions}

    return render(request, 'openplay/session_list.html', {
        'upcoming':        upcoming,
        'past':            past,
        'user_status_map': user_status_map,
    })


@login_required
def session_detail_view(request, pk):
    """Show session details and allow user to join/leave."""
    session = get_object_or_404(OpenPlaySession, pk=pk)

    # Get user's current participation status
    try:
        participant = OpenPlayParticipant.objects.get(
            session=session,
            user=request.user
        )
        user_participant = participant
    except OpenPlayParticipant.DoesNotExist:
        user_participant = None

    # Approved participants list (visible to all)
    approved = session.participants.filter(
        status=OpenPlayParticipant.Status.APPROVED
    ).select_related('user')

    # User's pending payment for this session (pay-to-join)
    pending_tx = None
    if user_participant:
        from transactions.models import Transaction
        pending_tx = Transaction.objects.filter(
            openplay=user_participant
        ).order_by('-created_at').first()

    from transactions.payments import payments_enabled
    return render(request, 'openplay/session_detail.html', {
        'session':          session,
        'user_participant': user_participant,
        'approved':         approved,
        'pending_tx':       pending_tx,
        'payments_enabled': payments_enabled(),
    })


@login_required
def join_session_view(request, pk):
    """User requests to join an open-play session."""
    session = get_object_or_404(OpenPlaySession, pk=pk)

    if request.method == 'POST':
        try:
            services.request_join(request.user, session)
            from transactions.payments import payments_enabled
            if payments_enabled() and session.fee > 0:
                messages.success(
                    request,
                    f'✅ Join request for "{session.title}" received. '
                    f'Complete payment to secure your spot.'
                )
            else:
                messages.success(
                    request,
                    f'✅ Join request sent for "{session.title}". '
                    f'Waiting for admin approval.'
                )
        except ValidationError as e:
            messages.error(request, e.message)

    return redirect('openplay:detail', pk=pk)


@login_required
def leave_session_view(request, pk):
    """User withdraws from an open-play session."""
    session = get_object_or_404(OpenPlaySession, pk=pk)

    if request.method == 'POST':
        try:
            services.leave_session(request.user, session)
            messages.success(request, 'You have left the session.')
        except ValidationError as e:
            messages.error(request, e.message)

    return redirect('openplay:detail', pk=pk)


# ── Admin Views ────────────────────────────────────────────────────────────────

@admin_or_staff_required
def admin_session_list_view(request):
    """Admin sees all sessions with participant counts."""
    from django.db.models import Count, Q

    sessions = OpenPlaySession.objects.annotate(
        pending_count=Count(
            'participants',
            filter=Q(participants__status=OpenPlayParticipant.Status.PENDING)
        )
    ).prefetch_related('participants').order_by('-date', '-start_time')

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        sessions = sessions.filter(status=status_filter)

    return render(request, 'openplay/admin_session_list.html', {
        'sessions':       sessions,
        'status_choices': OpenPlaySession.Status.choices,
        'status_filter':  status_filter,
    })


@admin_or_staff_required
def admin_session_create_view(request):
    """Admin creates a new open-play session."""
    form = OpenPlaySessionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        session = form.save(commit=False)
        session.created_by = request.user
        session.save()
        messages.success(request, f'Session "{session.title}" created.')
        return redirect('openplay:admin_detail', pk=session.pk)

    return render(request, 'openplay/session_form.html', {
        'form':  form,
        'title': 'Create Open Play Session',
    })


@admin_or_staff_required
def admin_session_edit_view(request, pk):
    """Admin edits an existing open-play session."""
    session = get_object_or_404(OpenPlaySession, pk=pk)
    form    = OpenPlaySessionForm(request.POST or None, instance=session)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Session updated.')
        return redirect('openplay:admin_detail', pk=pk)

    return render(request, 'openplay/session_form.html', {
        'form':    form,
        'title':   'Edit Session',
        'session': session,
    })


@admin_or_staff_required
def admin_session_detail_view(request, pk):
    """Admin manages participants for a session."""
    session      = get_object_or_404(OpenPlaySession, pk=pk)
    participants = session.participants.select_related('user').order_by(
        'status', 'joined_at'
    )
    add_form = AddParticipantForm()

    return render(request, 'openplay/admin_session_detail.html', {
        'session':      session,
        'participants': participants,
        'add_form':     add_form,
    })


@admin_or_staff_required
def admin_approve_view(request, pk, participant_id):
    """Admin approves a pending participant."""
    participant = get_object_or_404(
        OpenPlayParticipant, pk=participant_id, session_id=pk
    )

    if request.method == 'POST':
        try:
            services.approve_participant(participant)
            messages.success(
                request,
                f'{participant.user.full_name} approved.'
            )
        except ValidationError as e:
            messages.error(request, e.message)

    return redirect('openplay:admin_detail', pk=pk)


@admin_or_staff_required
def admin_reject_view(request, pk, participant_id):
    """Admin rejects a pending participant."""
    participant = get_object_or_404(
        OpenPlayParticipant, pk=participant_id, session_id=pk
    )

    if request.method == 'POST':
        services.reject_participant(participant)
        messages.warning(
            request,
            f'{participant.user.full_name} rejected.'
        )

    return redirect('openplay:admin_detail', pk=pk)


@admin_or_staff_required
def admin_add_participant_view(request, pk):
    """Admin manually adds a walk-in participant by name."""
    session = get_object_or_404(OpenPlaySession, pk=pk)

    if request.method == 'POST':
        form = AddParticipantForm(request.POST)
        if form.is_valid():
            try:
                participant = services.add_participant_manually(
                    admin_user=request.user,
                    session=session,
                    participant_name=form.cleaned_data['participant_name'],
                )
                messages.success(
                    request,
                    f'"{participant.display_name}" added to session.'
                )
            except ValidationError as e:
                messages.error(request, e.message)

    return redirect('openplay:admin_detail', pk=pk)


@admin_or_staff_required
def admin_session_complete_view(request, pk):
    """Admin marks session as completed."""
    session = get_object_or_404(OpenPlaySession, pk=pk)

    if request.method == 'POST':
        services.complete_session(session)
        messages.success(request, f'Session "{session.title}" marked as completed.')

    return redirect('openplay:admin_detail', pk=pk)


@admin_or_staff_required
def admin_session_cancel_view(request, pk):
    """Admin cancels a session."""
    session = get_object_or_404(OpenPlaySession, pk=pk)

    if request.method == 'POST':
        services.cancel_session(session)
        messages.warning(request, f'Session "{session.title}" cancelled.')

    return redirect('openplay:admin_detail', pk=pk)