"""Shared transaction actions."""
from django.utils import timezone

from .models import Transaction


def mark_transaction_paid(tx, provider=None):
    """
    Record a transaction as paid (counter / on-site collection).

    Idempotent: an already-paid transaction is returned untouched.
    `payment_method` is intentionally left alone so the table keeps
    showing the plain "On-site" badge for manual collections.
    """
    if tx is None:
        return None
    if tx.payment_status == Transaction.PaymentStatus.PAID:
        return tx

    tx.payment_status = Transaction.PaymentStatus.PAID
    tx.paid_at = timezone.now()

    fields = ['payment_status', 'paid_at', 'updated_at']
    if provider and tx.provider != provider:
        tx.provider = provider
        fields.append('provider')

    tx.save(update_fields=fields)
    return tx
