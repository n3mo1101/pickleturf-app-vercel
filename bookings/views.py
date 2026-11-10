from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.db import models
from django.db.models import Q
from django.views.decorators.http import require_GET
from courts.models import Court
from accounts.decorators import admin_or_staff_required
from core.utils import is_modal_request, safe_next_url
from .forms import BookingForm
from .models import Booking
from . import services
from transactions.payments import payments_enabled


# ── Customer Views ─────────────────────────────────────────────────────────────

@login_required
def availability_view(request):
    """Show court availability grid for a selected date."""
    selected_date_str = request.GET.get('date', date.today().isoformat())
    try:
        selected_date = date.fromisoformat(selected_date_str)
    except ValueError:
        selected_date = date.today()

    grid     = services.get_availability(selected_date)
    brackets = services.get_price_brackets_display()

    return render(request, 'bookings/availability.html', {
        'grid':          grid,
        'selected_date': selected_date,
        'today':         date.today().isoformat(),
        'brackets':      brackets,
    })


@login_required
def booking_create_view(request):
    from django.conf import settings as django_settings

    court_id      = request.GET.get('court') or request.POST.get('court')
    selected_date = request.GET.get('date')  or request.POST.get('date')
    requested_slots = (
        request.POST.getlist('time_slots')
        if request.method == 'POST'
        else request.GET.getlist('time')
    )

    court           = None
    available_slots = None
    parsed_date     = None
    preselected_slots = []
    brackets        = services.get_price_brackets_display()
    is_admin = getattr(request.user, 'is_admin_or_staff', False)

    if court_id and selected_date:
        try:
            court       = Court.objects.get(pk=court_id, is_active=True)
            parsed_date = date.fromisoformat(selected_date)
            available_slots = services.get_available_slots_for_court(
                court, parsed_date
            )
            valid_slot_values = {value for value, _ in available_slots}
            preselected_slots = [
                value for value in requested_slots if value in valid_slot_values
            ]
        except (Court.DoesNotExist, ValueError):
            court = None

    if request.method == 'POST':
        # Admin walk-in: hide online completely, force pay on-site
        effective_payments = False if is_admin else payments_enabled()
        form = BookingForm(request.POST, available_slots=available_slots, payments_enabled=effective_payments)

        if not form.is_valid():
            pass

        elif not form.cleaned_data.get('time_slots'):
            form.add_error('time_slots', 'Please select at least one slot.')

        else:
            data    = form.cleaned_data
            slots   = data['time_slots']
            payment_method = data.get('payment_method') or 'onsite'
            if is_admin:
                payment_method = 'onsite'
            elif not payments_enabled():
                payment_method = 'onsite'

            # Staff can settle the charge immediately (default: checked).
            mark_paid = bool(request.POST.get('mark_paid')) and is_admin

            try:
                booking = services.create_booking(
                    user=request.user,
                    court=data['court'],
                    selected_date=data['date'],
                    start_times=slots,
                    notes=data.get('notes', ''),
                    payment_method=payment_method,
                    mark_paid=mark_paid,
                )
            except ValidationError as e:
                form.add_error(None, str(e))
                messages.error(request, str(e))
            else:
                slot_count  = booking.slot_count
                total_price = booking.price
                if mark_paid:
                    messages.success(
                        request,
                        f'✅ {slot_count} slot(s) reserved on '
                        f'{parsed_date.strftime("%b %d, %Y")} '
                        f'for {data["court"]}. '
                        f'Total: ₱{total_price} — marked as paid.'
                    )
                elif payment_method == 'online' and payments_enabled() and not is_admin:
                    messages.success(
                        request,
                        f'✅ {slot_count} slot(s) reserved on '
                        f'{parsed_date.strftime("%b %d, %Y")} '
                        f'for {data["court"]}. '
                        f'Total: ₱{total_price} — redirecting to payment...'
                    )
                else:
                    messages.success(
                        request,
                        f'✅ {slot_count} slot(s) reserved on '
                        f'{parsed_date.strftime("%b %d, %Y")} '
                        f'for {data["court"]}. '
                        f'Total: ₱{total_price} — pay on-site.'
                    )

                if is_admin:
                    return redirect('bookings:admin_list')
                # One transaction covers the whole reservation.
                if payment_method == 'online' and payments_enabled():
                    try:
                        from django.conf import settings as _settings
                        base_url = (
                            _settings.SITE_URL
                            or request.build_absolute_uri('/')[:-1]
                        )
                        from transactions.payments import create_checkout
                        checkout_url = create_checkout(
                            booking.transaction, base_url=base_url
                        )
                        return redirect(checkout_url)
                    except Exception as e:
                        messages.warning(
                            request,
                            f'Online checkout not available: {e}. '
                            f'Use "Pay Now" on My Bookings.'
                        )
                return redirect('bookings:my_bookings')

    else:
        initial = {
            'court': court_id,
            'date': selected_date,
            'payment_method': 'onsite',
            'time_slots': preselected_slots,
        }
        effective_payments = False if is_admin else payments_enabled()
        form    = BookingForm(
            initial=initial, available_slots=available_slots, payments_enabled=effective_payments
        )

    return render(request, 'bookings/booking_form.html', {
        'form':           form,
        'title':          'Book a Court' if not is_admin else 'Book a Court (Walk-in)',
        'court':          court,
        'selected_date':  parsed_date,
        'slots_available': available_slots,
        'preselected_slots': preselected_slots,
        'brackets':       brackets,
        'payments_enabled': False if is_admin else payments_enabled(),
        'is_admin': is_admin,
    })


@login_required
def my_bookings_view(request):
    """Show logged-in user's booking history with summary and pagination."""
    services.auto_update_booking_statuses()  # Ensure statuses are up-to-date before fetching

    from django.core.paginator import Paginator
    from django.db.models import Count
    from transactions.models import Transaction

    all_bookings = (
        Booking.objects
        .filter(user=request.user)
        .select_related('court')
        .prefetch_related('slots')
        .order_by('-date', '-start_time')
    )

    # ── Summary (paid bookings only count as money spent) ──────────
    total_bookings = all_bookings.aggregate(
        total=Count('id')
    )['total'] or 0
    total_spent = (
        Transaction.objects
        .filter(
            booking__user=request.user,
            payment_status=Transaction.PaymentStatus.PAID,
        )
        .aggregate(total=models.Sum('amount'))['total'] or 0
    )

    # ── Pagination ─────────────────────────────────────────────────
    paginator = Paginator(all_bookings, 10)
    page      = request.GET.get('page', 1)
    bookings  = paginator.get_page(page)

    return render(request, 'bookings/my_bookings.html', {
        'bookings':       bookings,
        'total_bookings': total_bookings,
        'total_spent':    total_spent,
        'payments_enabled': payments_enabled(),
    })


@login_required
def booking_cancel_view(request, pk):
    """Customer cancels their own booking."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            services.cancel_booking(booking, cancelled_by=request.user)
            messages.success(request, 'Booking cancelled successfully.')
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('bookings:my_bookings')

    return redirect('bookings:my_bookings')


# ── Admin/Staff Views ──────────────────────────────────────────────────────────

@admin_or_staff_required
def admin_booking_list_view(request):
    """Admin view of all bookings with filters."""
    services.auto_update_booking_statuses()  # Keep statuses current on admin page load
    bookings = (
        Booking.objects
        .select_related('court', 'user')
        .prefetch_related('slots', 'transaction')
        .order_by('-date', '-start_time')
    )

    # Filters
    status_filter = request.GET.get('status')
    date_filter   = request.GET.get('date')
    court_filter  = request.GET.get('court')
    q             = request.GET.get('q', '').strip()

    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if date_filter:
        bookings = bookings.filter(date=date_filter)
    if court_filter:
        bookings = bookings.filter(court_id=court_filter)
    if q:
        bookings = bookings.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
        )

    return render(request, 'bookings/admin_booking_list.html', {
        'bookings':       bookings,
        'courts':         Court.objects.filter(is_active=True),
        'status_choices': Booking.Status.choices,
        'status_filter':  status_filter,
        'date_filter':    date_filter,
        'court_filter':   court_filter,
        'q':              q,
    })


@admin_or_staff_required
def admin_booking_create_view(request):
    """Deprecated admin booking — gracefully redirects to unified booking form."""
    from django.shortcuts import redirect
    return redirect('bookings:create')


@admin_or_staff_required
def admin_booking_cancel_view(request, pk):
    """Admin cancels any booking."""
    booking = get_object_or_404(Booking, pk=pk)

    redirect_url = request.POST.get('next') or 'bookings:admin_list'
    if not redirect_url.startswith('/') or redirect_url.startswith('//'):
        redirect_url = 'bookings:admin_list'

    if request.method == 'POST':
        try:
            services.cancel_booking(booking, cancelled_by=request.user)
            messages.success(request, f'Booking #{pk} cancelled.')
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect(redirect_url)

    return redirect(redirect_url)


@admin_or_staff_required
def admin_booking_status_view(request, pk):
    """Admin updates booking status and syncs slots/transaction."""
    booking = get_object_or_404(Booking, pk=pk)
    next_url = safe_next_url(
        request,
        request.POST.get('next') or request.GET.get('next'),
    )

    if request.method == 'POST':
        new_status = request.POST.get('status')

        try:
            services.set_booking_status(booking, new_status)
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect(next_url or 'bookings:admin_list')

        messages.success(
            request,
            f'Booking #{pk} status updated to '
            f'{booking.get_status_display()}.'
        )
        return redirect(next_url or 'bookings:admin_list')

    template = (
        'bookings/_booking_status_modal.html'
        if is_modal_request(request)
        else 'bookings/admin_booking_status.html'
    )
    return render(request, template, {
        'booking':        booking,
        'status_choices': Booking.EDITABLE_STATUSES,
        'next':           next_url or '',
    })


@admin_or_staff_required
def staff_bookings_view(request):
    """
    Show bookings created by the logged-in staff member.
    Useful for staff to track bookings they personally processed.
    """
    from django.core.paginator import Paginator

    services.auto_update_booking_statuses()

    bookings = (
        Booking.objects
        .filter(created_by=request.user)
        .select_related('court', 'user')
        .prefetch_related('slots', 'transaction')
        .order_by('-date', '-start_time')
    )

    status_filter = request.GET.get('status')
    date_filter   = request.GET.get('date')
    court_filter  = request.GET.get('court')
    q             = request.GET.get('q', '').strip()

    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if date_filter:
        bookings = bookings.filter(date=date_filter)
    if court_filter:
        bookings = bookings.filter(court_id=court_filter)
    if q:
        bookings = bookings.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
        )

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    paginator = Paginator(bookings, 10)
    page      = request.GET.get('page', 1)
    bookings  = paginator.get_page(page)

    return render(request, 'bookings/staff_bookings.html', {
        'bookings':       bookings,
        'courts':         Court.objects.filter(is_active=True),
        'status_choices': Booking.Status.choices,
        'status_filter':  status_filter,
        'date_filter':    date_filter,
        'court_filter':   court_filter,
        'q':              q,
        'query_string':   query_string,
    })


# ── Cron ───────────────────────────────────────────────────────────────────────

@require_GET
def cron_update_statuses(request):
    """
    Called hourly by Vercel Cron. Protected by CRON_SECRET:
    Vercel sends `Authorization: Bearer <CRON_SECRET>` on each invocation.
    """
    from django.conf import settings as django_settings
    from django.http import JsonResponse

    secret = django_settings.CRON_SECRET
    if not secret:
        return JsonResponse({'error': 'CRON_SECRET not configured'}, status=503)

    if request.META.get('HTTP_AUTHORIZATION', '') != f'Bearer {secret}':
        return JsonResponse({'error': 'unauthorized'}, status=401)

    services.auto_update_booking_statuses()

    from openplay.services import auto_update_session_statuses
    auto_update_session_statuses()

    return JsonResponse({'status': 'ok'})