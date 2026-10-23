from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import InventoryItem, RentalRecord, Sale, SaleItem


# ── Stock Adjustment ───────────────────────────────────────────────────────────

def adjust_stock(item, quantity, action='add'):
    """Manually adjust stock. action: 'add' or 'deduct'."""
    if action == 'deduct':
        if item.stock < quantity:
            raise ValidationError(
                f'Insufficient stock. Only {item.stock} '
                f'unit(s) of "{item.name}" available.'
            )
        item.stock -= quantity
    elif action == 'add':
        item.stock += quantity
    else:
        raise ValueError('action must be "add" or "deduct"')

    item.save(update_fields=['stock'])
    return item


# ── POS Sale ───────────────────────────────────────────────────────────────────

def process_sale(cart_items, created_by=None, notes=''):
    """
    Process a POS sale from a list of cart items.

    cart_items: list of dicts → [{'item': InventoryItem, 'quantity': int}, ...]

    Steps:
      1. Validate all stock levels before touching anything
      2. Create Sale header
      3. Create SaleItem line items + deduct stock
      4. Compute total
      5. Create one Transaction record
    """
    if not cart_items:
        raise ValidationError('Cart is empty.')

    # ── Step 1: Validate everything first ─────────────────────────
    for entry in cart_items:
        item = entry['item']
        qty  = entry['quantity']

        if item.item_type not in (
            InventoryItem.ItemType.SALE,
            InventoryItem.ItemType.BOTH
        ):
            raise ValidationError(f'"{item.name}" is not available for sale.')

        if not item.sale_price:
            raise ValidationError(f'"{item.name}" has no sale price set.')

        if item.stock < qty:
            raise ValidationError(
                f'Insufficient stock for "{item.name}". '
                f'Available: {item.stock}, requested: {qty}.'
            )

    # ── Step 2: Create Sale header ─────────────────────────────────
    sale = Sale.objects.create(created_by=created_by, notes=notes)

    # ── Step 3: Create line items + deduct stock ───────────────────
    for entry in cart_items:
        item = entry['item']
        qty  = entry['quantity']

        SaleItem.objects.create(
            sale=sale,
            item=item,
            quantity=qty,
            unit_price=item.sale_price,
        )
        item.deduct_stock(qty)

    # ── Step 4: Compute total ──────────────────────────────────────
    sale.compute_total()

    # ── Step 5: Create transaction ─────────────────────────────────
    _create_sale_transaction(sale, created_by)

    return sale


def _create_sale_transaction(sale, created_by=None):
    """Log one Transaction record for the entire sale."""
    from transactions.models import Transaction

    item_summary = ', '.join(
        f'{si.item.name} x{si.quantity}'
        for si in sale.items.select_related('item')
    )
    Transaction.objects.create(
        user=None,                         # no user linked for walk-in sales
        tx_type=Transaction.TxType.SALE,
        amount=sale.total,
        sale=sale,
        payment_status=Transaction.PaymentStatus.PAID,
        description=item_summary,
        created_by=created_by,
    )


# ── Rental POS ─────────────────────────────────────────────────────────────────

def process_rental(cart_items, renter_name, renter_contact='', handled_by=None):
    """
    Process a POS-style rental from a list of cart items.

    cart_items: [{'item': InventoryItem, 'quantity': int}, ...]

    Steps:
      1. Validate all items and stock before touching anything
      2. Create one RentalRecord per line item + deduct stock
      3. Create one combined Transaction for the whole checkout
    """
    if not cart_items:
        raise ValidationError('No items selected.')

    if not renter_name or not renter_name.strip():
        raise ValidationError('Renter name is required.')

    # ── Step 1: Validate everything first ─────────────────────────
    for entry in cart_items:
        item = entry['item']
        qty  = entry['quantity']

        if item.item_type not in (
            InventoryItem.ItemType.RENT,
            InventoryItem.ItemType.BOTH,
        ):
            raise ValidationError(
                f'"{item.name}" is not available for rent.'
            )

        if not item.rent_price:
            raise ValidationError(
                f'"{item.name}" has no rental price set.'
            )

        if item.stock < qty:
            raise ValidationError(
                f'Insufficient stock for "{item.name}". '
                f'Available: {item.stock}, requested: {qty}.'
            )

    # ── Step 2: Create rental records + deduct stock ───────────────
    records    = []
    grand_total = 0

    for entry in cart_items:
        item = entry['item']
        qty  = entry['quantity']

        item.deduct_stock(qty)

        record = RentalRecord.objects.create(
            item=item,
            quantity=qty,
            renter_name=renter_name.strip(),
            renter_contact=renter_contact.strip(),
            handled_by=handled_by,
        )
        records.append(record)
        grand_total += record.total_cost

    # ── Step 3: One combined transaction ──────────────────────────
    _create_rental_transaction_bulk(
        records, grand_total, renter_name, handled_by
    )

    return records, grand_total


def _create_rental_transaction_bulk(
    records, grand_total, renter_name, handled_by=None
):
    """One Transaction record covering all items in a rental checkout."""
    from transactions.models import Transaction

    item_summary = ', '.join(
        f'{r.item.name} x{r.quantity}' for r in records
    )

    Transaction.objects.create(
        user=None,
        tx_type=Transaction.TxType.RENTAL,
        amount=grand_total,
        payment_status=Transaction.PaymentStatus.PAID,
        description=(
            f'{item_summary} '
            f'({renter_name})'
        ),
        created_by=handled_by,
    )


def return_rental(rental, handled_by=None):
    """Mark rental returned and restore stock."""
    if rental.status == RentalRecord.Status.RETURNED:
        raise ValidationError('This item has already been returned.')

    rental.status      = RentalRecord.Status.RETURNED
    rental.returned_at = timezone.now()
    if handled_by:
        rental.handled_by = handled_by
    rental.save(update_fields=['status', 'returned_at', 'handled_by'])

    rental.item.add_stock(rental.quantity)   # ← restore quantity, not just 1
    return rental