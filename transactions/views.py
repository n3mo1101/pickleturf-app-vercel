from datetime import date
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import logging
import json

logger = logging.getLogger(__name__)

from accounts.decorators import admin_or_staff_required
from bookings.models import Booking
from .models import Transaction
from . import payments


@admin_or_staff_required
def transaction_list_view(request):
    """
    Admin transaction history with:
    - Date range filter
    - Type and status filters
    - Running total of filtered results
    - Pagination (20 per page)
    """
    transactions = Transaction.objects.select_related(
        'user', 'created_by'
    ).order_by('-created_at')

    # ── Filters ────────────────────────────────────────────────────
    type_filter   = request.GET.get('type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from     = request.GET.get('date_from', '').strip()
    date_to       = request.GET.get('date_to', '').strip()

    if type_filter:
        transactions = transactions.filter(tx_type=type_filter)
    if status_filter:
        transactions = transactions.filter(payment_status=status_filter)
    if date_from:
        try:
            transactions = transactions.filter(
                created_at__date__gte=date_from
            )
        except ValueError:
            pass
    if date_to:
        try:
            transactions = transactions.filter(
                created_at__date__lte=date_to
            )
        except ValueError:
            pass

    # ── Running Total of Filtered Results ─────────────────────────
    filtered_total = transactions.aggregate(
        total=Sum('amount'),
        count=Count('id'),
    )
    total_amount = filtered_total['total'] or 0
    total_count  = filtered_total['count'] or 0

    # ── Pagination ─────────────────────────────────────────────────
    paginator    = Paginator(transactions, 20)
    page         = request.GET.get('page', 1)
    transactions = paginator.get_page(page)

    # Build query string for pagination links (preserve filters)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    return render(request, 'transactions/list.html', {
        'transactions':   transactions,
        'type_choices':   Transaction.TxType.choices,
        'status_choices': Transaction.PaymentStatus.choices,
        'type_filter':    type_filter,
        'status_filter':  status_filter,
        'date_from':      date_from,
        'date_to':        date_to,
        'total_amount':   total_amount,
        'total_count':    total_count,
        'query_string':   query_string,
    })


@admin_or_staff_required
def mark_paid_view(request, pk):
    """
    Manually mark a transaction as Paid (on-site / manual payments).
    A linked booking is only completed if its slot has already passed.
    """
    from datetime import datetime as dt
    from django.utils import timezone

    transaction = get_object_or_404(Transaction, pk=pk)

    if request.method == 'POST':
        if not transaction.paid_at:
            transaction.paid_at = timezone.now()
        transaction.payment_status = Transaction.PaymentStatus.PAID
        transaction.save(update_fields=['payment_status', 'paid_at'])

        booking_completed = False
        if transaction.booking:
            booking = transaction.booking
            slot_dt = timezone.make_aware(
                dt.combine(booking.date, booking.start_time)
            )
            if slot_dt <= timezone.now() and booking.status not in (
                Booking.Status.COMPLETED, Booking.Status.CANCELLED
            ):
                booking.status = Booking.Status.COMPLETED
                booking.save(update_fields=['status'])
                booking_completed = True
            messages.success(
                request,
                f'Transaction #{pk} marked as paid.'
                + (' Booking #{booking.pk} completed.'
                   if booking_completed else ''),
            )
        else:
            messages.success(request, f'Transaction #{pk} marked as paid.')

    # Preserve filters when redirecting back (relative path only)
    redirect_url = request.POST.get('next') or 'transactions:list'
    if not redirect_url.startswith('/') or redirect_url.startswith('//'):
        redirect_url = 'transactions:list'
    return redirect(redirect_url)


# ── Online Payment (PayMongo / GCash) ──────────────────────────────────────────

def _back_url(transaction):
    """Where to send the user back to after checkout/cancel."""
    if transaction.booking:
        return ('bookings:my_bookings', ())
    if transaction.openplay:
        return ('openplay:detail', (transaction.openplay.session_id,))
    return ('transactions:list', ())


@login_required
def checkout_view(request, pk):
    """Create a PayMongo hosted checkout session and redirect to it."""
    tx = get_object_or_404(Transaction, pk=pk)

    # Only the owner (or an admin/staff member) may pay a transaction.
    if tx.user and tx.user != request.user and not request.user.is_admin_or_staff:
        messages.error(request, 'You are not allowed to pay this transaction.')
        return redirect('core:home')
    if not tx.user and not request.user.is_admin_or_staff:
        messages.error(request, 'You are not allowed to pay this transaction.')
        return redirect('core:home')

    if tx.tx_type not in (Transaction.TxType.BOOKING, Transaction.TxType.OPENPLAY):
        messages.error(request, 'This transaction cannot be paid online.')
        back_name, back_args = _back_url(tx)
        return redirect(back_name, *back_args)

    try:
        base_url = settings.SITE_URL or request.build_absolute_uri('/')[:-1]
        checkout_url = payments.create_checkout(tx, base_url=base_url)
    except Exception as e:
        messages.error(request, str(e))
        back_name, back_args = _back_url(tx)
        return redirect(back_name, *back_args)

    return redirect(checkout_url)


@login_required
def payment_result_view(request, pk, outcome):
    """Friendly page shown after returning from the payment provider."""
    tx = get_object_or_404(Transaction, pk=pk)

    if tx.user and tx.user != request.user and not request.user.is_admin_or_staff:
        messages.error(request, 'You are not allowed to view this transaction.')
        return redirect('core:home')

    # Fallback polling: if webhook missed and checkout is paid, fulfill now
    if outcome == 'success' and tx.payment_status == Transaction.PaymentStatus.PENDING and tx.provider_checkout_id:
        try:
            import requests
            from . import payments as _payments
            # Try to fetch checkout session status directly from PayMongo
            base = settings.PAYMONGO_API_BASE or 'https://api.paymongo.com'
            # Use v1 checkout_sessions retrieval (PayMongo supports both v1/v2)
            resp = requests.get(
                f'{base}/v1/checkout_sessions/{tx.provider_checkout_id}',
                headers=_payments._api_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                cs_data = resp.json().get('data', {})
                attrs = cs_data.get('attributes') or {}
                # If checkout is paid, it will have payments array with paid status
                payments = attrs.get('payments') or []
                is_paid = any((p.get('attributes') or {}).get('status') == 'paid' for p in payments) or attrs.get('paid_at') or attrs.get('status') == 'active' and payments
                if payments and attrs.get('reference_number') == str(tx.pk):
                    # Reuse webhook fulfillment path with checkout attributes
                    _payments.handle_webhook_payload({
                        'data': {
                            'type': 'checkout_session.payment.paid',
                            'data': {'id': cs_data.get('id'), 'attributes': attrs}
                        }
                    })
                    tx.refresh_from_db()
                    logger.info("payment_result polling fulfilled tx=%s status=%s", tx.pk, tx.payment_status)
        except Exception as e:
            logger.warning("payment_result polling failed tx=%s err=%s", tx.pk, e)

    return render(request, 'transactions/payment_result.html', {
        'transaction': tx,
        'outcome':     outcome if outcome in ('success', 'cancelled') else 'cancelled',
    })


@csrf_exempt
def webhook_view(request):
    """PayMongo webhook endpoint — signature-verified payment events."""
    if request.method != 'POST':
        logger.warning("webhook non-POST %s", request.method)
        return HttpResponseForbidden('Method not allowed')

    payload = request.body.decode('utf-8', errors='replace')
    header = (
        request.headers.get('Paymongo-Webhook-Signature')
        or request.headers.get('Paymongo-Signature')
        or ''
    )

    if not payments.verify_webhook_signature(payload, header):
        logger.warning("webhook invalid sig header=%s payload_prefix=%s", header[:200], payload[:500])
        return HttpResponseForbidden('Invalid signature')

    try:
        data = json.loads(payload)
    except ValueError:
        logger.warning("webhook invalid JSON payload=%s", payload[:1000])
        return HttpResponseForbidden('Invalid payload')

    logger.info("webhook received header=%s payload_type=%s", header[:150], (data.get('data') or {}).get('type'))
    result = payments.handle_webhook_payload(data)
    if result:
        logger.info("webhook handled tx=%s status=%s", result.pk, result.payment_status)
        return HttpResponse(f'OK tx={result.pk} paid')
    else:
        # Still 200 to avoid PayMongo retry storm, but log for debugging
        logger.warning("webhook handled but no tx fulfilled payload=%s", payload[:2000])
        return HttpResponse('OK ignored: no tx matched')