import csv
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import admin_or_staff_required
from bookings.models import Booking
from inventory.models import RentalRecord
from openplay.models import OpenPlaySession
from transactions.models import Transaction
from transactions.utils import strip_tx_prefix


# ── Helpers ────────────────────────────────────────────────────────────────────

_TX_TYPE_SHORT = {
    Transaction.TxType.BOOKING:  'Booking',
    Transaction.TxType.OPENPLAY: 'Open Play',
    Transaction.TxType.SALE:     'Sale',
    Transaction.TxType.RENTAL:   'Rental',
    Transaction.TxType.MANUAL:   'Manual',
}


def _revenue_queryset():
    """Base queryset — only paid or pending (on-site) transactions count."""
    return Transaction.objects.filter(
        payment_status__in=[
            Transaction.PaymentStatus.PENDING,
            Transaction.PaymentStatus.PAID,
        ]
    )


def _daily_revenue_last_30():
    """
    Returns list of (date_str, total) for last 30 days.
    Fills in 0 for days with no transactions.
    """
    today   = date.today()
    start   = today - timedelta(days=29)

    rows = (
        _revenue_queryset()
        .filter(created_at__date__gte=start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )

    # Build a lookup dict
    lookup = {r['day']: float(r['total']) for r in rows}

    labels, data = [], []
    for i in range(30):
        d = start + timedelta(days=i)
        labels.append(d.strftime('%b %d'))
        data.append(lookup.get(d, 0))

    return labels, data


def _monthly_revenue_this_year():
    """Returns list of 12 monthly totals for the current year."""
    year = date.today().year

    rows = (
        _revenue_queryset()
        .filter(created_at__year=year)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    lookup = {r['month'].month: float(r['total']) for r in rows}

    months = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']
    data   = [lookup.get(m, 0) for m in range(1, 13)]

    return months, data


def _revenue_by_type():
    """Returns revenue broken down by transaction type."""
    rows = (
        _revenue_queryset()
        .values('tx_type')
        .annotate(total=Sum('amount'))
    )

    type_map = dict(Transaction.TxType.choices)
    labels   = [type_map.get(r['tx_type'], r['tx_type']) for r in rows]
    data     = [float(r['total']) for r in rows]

    return labels, data


# ── Main Dashboard View ────────────────────────────────────────────────────────

@admin_or_staff_required
def index(request):
    # Update booking statuses before loading dashboard data
    from bookings.services import auto_update_booking_statuses
    auto_update_booking_statuses()

    today = date.today()
    now   = timezone.now()

    # ── Summary Cards ──────────────────────────────────────────────
    today_qs = _revenue_queryset().filter(created_at__date=today)

    today_revenue = today_qs.aggregate(total=Sum('amount'))['total'] or 0

    split_bookings = (
        today_qs
        .filter(tx_type__in=[
            Transaction.TxType.BOOKING,
            Transaction.TxType.OPENPLAY,
        ])
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    split_products = (
        today_qs
        .filter(tx_type__in=[
            Transaction.TxType.SALE,
            Transaction.TxType.RENTAL,
        ])
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    last_tx = today_qs.order_by('-created_at').first()
    last_tx_amount = last_tx.amount if last_tx else None
    last_tx_label = _TX_TYPE_SHORT.get(last_tx.tx_type) if last_tx else None

    month_revenue = (
        _revenue_queryset()
        .filter(
            created_at__year=today.year,
            created_at__month=today.month
        )
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    bookings_today = Booking.objects.filter(
        date=today,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
    ).count()

    active_rentals = RentalRecord.objects.filter(
        status=RentalRecord.Status.ACTIVE
    ).count()

    # ── Chart Data ─────────────────────────────────────────────────
    daily_labels,   daily_data   = _daily_revenue_last_30()
    monthly_labels, monthly_data = _monthly_revenue_this_year()
    type_labels,    type_data    = _revenue_by_type()

    # ── Recent Activity ────────────────────────────────────────────
    recent_transactions = (
        Transaction.objects
        .select_related('user')
        .order_by('-created_at')[:7]
    )

    todays_bookings = (
        Booking.objects
        .filter(
            date=today,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
        )
        .select_related('court', 'user')
        .order_by('start_time')
    )

    upcoming_sessions = (
        OpenPlaySession.objects
        .filter(
            date__gte=today,
            status__in=[
                OpenPlaySession.Status.OPEN,
                OpenPlaySession.Status.FULL,
            ]
        )
        .order_by('date', 'start_time')[:3]
    )

    context = {
        # Cards
        'today_revenue':    today_revenue,
        'split_bookings':   split_bookings,
        'split_products':   split_products,
        'last_tx_amount':   last_tx_amount,
        'last_tx_label':    last_tx_label,
        'month_revenue':    month_revenue,
        'bookings_today':   bookings_today,
        'active_rentals':   active_rentals,

        # Charts (passed as Python lists — serialized in template)
        'daily_labels':   daily_labels,
        'daily_data':     daily_data,
        'monthly_labels': monthly_labels,
        'monthly_data':   monthly_data,
        'type_labels':    type_labels,
        'type_data':      type_data,

        # Tables
        'recent_transactions': recent_transactions,
        'todays_bookings':     todays_bookings,
        'upcoming_sessions':   upcoming_sessions,

        # Meta
        'today': today,
    }

    return render(request, 'dashboard/index.html', context)


# ── CSV Export (modal-driven) ──────────────────────────────────────────────────

_EXPORT_TYPES = ('transactions', 'daily', 'monthly')
_EXPORT_FILENAMES = {
    'transactions': 'transactions',
    'daily':        'daily_revenue',
    'monthly':      'monthly_revenue',
}


def _export_range(request):
    """Parse optional start/end date query params (YYYY-MM-DD). Raises ValueError."""
    start = request.GET.get('start') or None
    end   = request.GET.get('end') or None
    try:
        if start:
            start = date.fromisoformat(start)
        if end:
            end = date.fromisoformat(end)
    except ValueError:
        raise ValueError('Invalid date range')
    return start, end


def _export_filename(kind, start, end):
    suffix = f'{start}_{end}' if (start or end) else 'all'
    return f'{_EXPORT_FILENAMES[kind]}_{suffix}.csv'


def _filter_by_range(queryset, field, start, end):
    if start:
        queryset = queryset.filter(**{f'{field}__gte': start})
    if end:
        queryset = queryset.filter(**{f'{field}__lte': end})
    return queryset


@admin_or_staff_required
def export_csv(request):
    """Unified export driven by the export modal: ?type=&start=&end="""
    kind = request.GET.get('type')

    if kind not in _EXPORT_TYPES:
        return HttpResponse('Invalid export type', status=400)

    try:
        start, end = _export_range(request)
    except ValueError:
        return HttpResponse('Invalid date range', status=400)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="{_export_filename(kind, start, end)}"'
    )
    writer = csv.writer(response)

    if kind == 'transactions':
        rows = _filter_by_range(
            Transaction.objects
            .select_related('user', 'created_by')
            .order_by('-created_at'),
            'created_at__date', start, end,
        )
        writer.writerow([
            'ID', 'Date', 'Type', 'Amount',
            'Payment Status', 'Description', 'Created By',
        ])
        for tx in rows:
            writer.writerow([
                tx.pk,
                tx.created_at.strftime('%Y-%m-%d %H:%M'),
                tx.get_tx_type_display(),
                tx.amount,
                tx.get_payment_status_display(),
                strip_tx_prefix(tx.description),
                tx.created_by.email if tx.created_by else '—',
            ])


    elif kind == 'daily':
        rows = _filter_by_range(
            _revenue_queryset(),
            'created_at__date', start, end,
        )
        writer.writerow(['Date', 'Total'])
        for r in (
            rows
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Sum('amount'))
            .order_by('day')
        ):
            writer.writerow([r['day'].strftime('%Y-%m-%d'), r['total']])


    else:  # monthly
        rows = _filter_by_range(
            _revenue_queryset(),
            'created_at__date', start, end,
        )
        writer.writerow(['Month', 'Total'])
        for r in (
            rows
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        ):
            writer.writerow([r['month'].strftime('%Y-%m'), r['total']])

    return response