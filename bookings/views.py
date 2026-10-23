from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.db import models
from django.utils import timezone
from courts.models import Court
from accounts.decorators import admin_or_staff_required
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

    court           = None
    available_slots = None
    parsed_date     = None
    brackets        = services.get_price_brackets_display()
    is_admin = getattr(request.user, 'is_admin_or_staff', False)

    if court_id and selected_date:
        try:
            court       = Court.objects.get(pk=court_id, is_active=True)
            parsed_date = date.fromisoformat(selected_date)
            available_slots = services.get_available_slots_for_court(
                court, parsed_date
            )
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
            created = []
            errors  = []

            for slot_str in slots:
                try:
                    t = datetime.strptime(slot_str, '%H:%M:%S').time()
                    booking = services.create_booking(
                        user=request.user,
                        court=data['court'],
                        selected_date=data['date'],
                        start_time=t,
                        notes=data.get('notes', ''),
                        payment_method=payment_method,
                    )
                    created.append(booking)
                except ValidationError as e:
                    errors.append(str(e.message))

            if created:
                total_price = sum(b.price for b in created)
                if payment_method == 'online' and payments_enabled() and not is_admin:
                    messages.success(
                        request,
                        f'✅ {len(created)} slot(s) reserved on '
                        f'{parsed_date.strftime("%b %d, %Y")} '
                        f'for {data["court"]}. '
                        f'Total: ₱{total_price} — redirecting to payment...'
                    )
                else:
                    messages.success(
                        request,
                        f'✅ {len(created)} slot(s) booked on '
                        f'{parsed_date.strftime("%b %d, %Y")} '
                        f'for {data["court"]}. '
                        f'Total: ₱{total_price} — confirmed, pay on-site.'
                    )
            for err in errors:
                messages.warning(request, f'⚠️ Skipped: {err}')

            if created:
                if is_admin:
                    return redirect('bookings:admin_list')
                # Online → redirect directly to PayMongo checkout for first booking
                if payment_method == 'online' and payments_enabled():
                    try:
                        first_tx = created[0].transaction
                        # If multiple slots, remaining Pay Now buttons stay on My Bookings
                        if len(created) > 1:
                            messages.info(request, f'{len(created)-1} other slot(s) can be paid via "Pay Now" on My Bookings.')
                        from django.conf import settings as _settings
                        base_url = _settings.SITE_URL or request.build_absolute_uri('/')[:-1]
                        from transactions.payments import create_checkout
                        checkout_url = create_checkout(first_tx, base_url=base_url)
                        return redirect(checkout_url)
                    except Exception as e:
                        messages.warning(request, f'Online checkout not available: {e}. Use "Pay Now" on My Bookings.')
                return redirect('bookings:my_bookings')

    else:
        initial = {'court': court_id, 'date': selected_date, 'payment_method': 'onsite'}
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
        'brackets':       brackets,
        'payments_enabled': False if is_admin else payments_enabled(),
        'is_admin': is_admin,
    })


@login_required
def my_bookings_view(request):
    """Show logged-in user's booking history with summary and pagination."""
    services.auto_update_booking_statuses()  # Ensure statuses are up-to-date before fetching

    from django.core.paginator import Paginator
    from django.db.models import Sum, Count

    all_bookings = (
        Booking.objects
        .filter(user=request.user)
        .select_related('court')
        .order_by('-date', '-start_time')
    )

    # ── Summary ────────────────────────────────────────────────────
    summary = all_bookings.aggregate(
        total_bookings=Count('id'),
        total_spent=Sum(
            'price',
            filter=models.Q(
                status__in=[
                    Booking.Status.CONFIRMED,
                    Booking.Status.COMPLETED,
                ]
            )
        )
    )

    # ── Pagination ─────────────────────────────────────────────────
    paginator = Paginator(all_bookings, 10)
    page      = request.GET.get('page', 1)
    bookings  = paginator.get_page(page)

    return render(request, 'bookings/my_bookings.html', {
        'bookings':       bookings,
        'total_bookings': summary['total_bookings'] or 0,
        'total_spent':    summary['total_spent']    or 0,
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
    bookings = Booking.objects.select_related('court', 'user').order_by('-date', '-start_time')

    # Filters
    status_filter = request.GET.get('status')
    date_filter   = request.GET.get('date')
    court_filter  = request.GET.get('court')

    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if date_filter:
        bookings = bookings.filter(date=date_filter)
    if court_filter:
        bookings = bookings.filter(court_id=court_filter)

    return render(request, 'bookings/admin_booking_list.html', {
        'bookings':       bookings,
        'courts':         Court.objects.filter(is_active=True),
        'status_choices': Booking.Status.choices,
        'status_filter':  status_filter,
        'date_filter':    date_filter,
        'court_filter':   court_filter,
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

    if request.method == 'POST':
        try:
            services.cancel_booking(booking, cancelled_by=request.user)
            messages.success(request, f'Booking #{pk} cancelled.')
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('bookings:admin_list')

    return redirect('bookings:admin_list')


@admin_or_staff_required
def admin_booking_status_view(request, pk):
    """Admin updates booking status and syncs the linked transaction."""
    from transactions.models import Transaction

    booking = get_object_or_404(Booking, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status not in dict(Booking.Status.choices):
            messages.error(request, 'Invalid status.')
            return redirect('bookings:admin_list')

        booking.status = new_status
        if new_status == Booking.Status.CANCELLED:
            booking.cancelled_at = timezone.now()
        booking.save(update_fields=['status', 'cancelled_at'])

        # ── Sync linked transaction payment status ─────────────────
        try:
            tx = booking.transaction
            if new_status == Booking.Status.CONFIRMED:
                tx.payment_status = Transaction.PaymentStatus.PENDING
            elif new_status == Booking.Status.COMPLETED:
                tx.payment_status = Transaction.PaymentStatus.PAID
            elif new_status == Booking.Status.CANCELLED:
                tx.payment_status = Transaction.PaymentStatus.REFUNDED
            else:
                tx.payment_status = Transaction.PaymentStatus.WAIVED
            tx.save(update_fields=['payment_status'])
        except Exception:
            pass   # no transaction linked — safe to ignore

        messages.success(
            request,
            f'Booking #{pk} status updated to '
            f'{booking.get_status_display()}.'
        )
        return redirect('bookings:admin_list')

    return render(request, 'bookings/admin_booking_status.html', {
        'booking':        booking,
        'status_choices': Booking.Status.choices,
    })


@admin_or_staff_required
def staff_bookings_view(request):
    """
    Show bookings created by the logged-in staff member.
    Useful for staff to track bookings they personally processed.
    """
    from django.core.paginator import Paginator

    bookings = (
        Booking.objects
        .filter(created_by=request.user)
        .select_related('court', 'user')
        .order_by('-date', '-start_time')
    )

    paginator = Paginator(bookings, 10)
    page      = request.GET.get('page', 1)
    bookings  = paginator.get_page(page)

    return render(request, 'bookings/staff_bookings.html', {
        'bookings': bookings,
    })