from django.db import models
from django.conf import settings


class Transaction(models.Model):

    class TxType(models.TextChoices):
        BOOKING  = 'booking',  'Court Booking'
        RENTAL   = 'rental',   'Equipment Rental'
        SALE     = 'sale',     'Item Sale'
        OPENPLAY = 'openplay', 'Open Play'
        MANUAL   = 'manual',   'Manual Entry'

    class PaymentStatus(models.TextChoices):
        PENDING  = 'pending',  'Pending Payment'
        PAID     = 'paid',     'Paid'
        REFUNDED = 'refunded', 'Refunded'
        WAIVED   = 'waived',   'Waived'

    class Provider(models.TextChoices):
        PAYMONGO = 'paymongo', 'PayMongo (Online)'
        ONSITE   = 'onsite',   'On-site / Manual'

    # ── Who & What ─────────────────────────────────────────────────
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions'
    )
    tx_type      = models.CharField(max_length=20, choices=TxType.choices)
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    description  = models.TextField(blank=True)

    # ── Payment provider details ────────────────────────────────
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.ONSITE
    )
    provider_checkout_id = models.CharField(
        max_length=50, blank=True,
        help_text='PayMongo checkout session id (cs_...)'
    )
    provider_payment_id = models.CharField(
        max_length=50, null=True, blank=True, unique=True,
        help_text='PayMongo payment id (pay_...)'
    )
    payment_method = models.CharField(
        max_length=20, blank=True,
        help_text='e.g. gcash, card, qrph, onsite'
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    # ── Optional Links to source records ──────────────────────────
    booking      = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transaction'
    )
    rental       = models.OneToOneField(
        'inventory.RentalRecord',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transaction'
    )
    sale = models.ForeignKey(
        'inventory.Sale',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions'
    )
    openplay     = models.ForeignKey(
        'openplay.OpenPlayParticipant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions'
    )

    # ── Audit ──────────────────────────────────────────────────────
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions_created'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    notes        = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['tx_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f'{self.get_tx_type_display()} | {self.user} | ₱{self.amount}'