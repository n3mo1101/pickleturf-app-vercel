/* static/js/pos.js
   Shared POS cart logic for Sales and Rental POS pages.
   Expects either .pos-item-card or .rental-item-card elements.
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    const isSale      = !!document.getElementById('pos-form');
    const formId      = isSale ? 'pos-form' : 'rental-form';
    const cardClass   = isSale ? '.pos-item-card' : '.rental-item-card';
    const priceColor  = isSale ? 'text-success' : 'text-warning';
    const borderClass = isSale ? 'border-success' : 'border-warning';

    const qtyInputs   = document.querySelectorAll('.qty-input');
    const cartLines   = document.getElementById('cart-lines');
    const cartEmpty   = document.getElementById('cart-empty');
    const grandTotal  = document.getElementById('grand-total');
    const checkoutBtn = document.getElementById('checkout-btn');

    function updateCart() {
        cartLines.querySelectorAll('.cart-line').forEach(el => el.remove());

        let total    = 0;
        let hasItems = false;

        qtyInputs.forEach(input => {
            const qty = parseInt(input.value) || 0;
            if (qty <= 0) return;

            const card  = input.closest(cardClass);
            const name  = card.dataset.name;
            const price = parseFloat(card.dataset.price) || 0;
            const sub   = price * qty;
            total      += sub;
            hasItems    = true;

            const line = document.createElement('div');
            line.className = 'list-group-item cart-line d-flex justify-content-between align-items-start py-2';
            line.innerHTML = `
                <div>
                    <div class="fw-semibold small">${name}</div>
                    <div class="text-muted" style="font-size:.75rem;">
                        ₱${price.toLocaleString()} × ${qty}
                    </div>
                </div>
                <span class="fw-bold ${priceColor} small">
                    ₱${sub.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>`;
            cartLines.insertBefore(line, cartEmpty);
        });

        cartEmpty.style.display = hasItems ? 'none' : '';

        const fmtTotal = total.toLocaleString(undefined, { minimumFractionDigits: 2 });
        if (grandTotal) grandTotal.textContent = fmtTotal;
        if (checkoutBtn) {
            checkoutBtn.disabled = !hasItems;
            checkoutBtn.innerHTML = hasItems
                ? `<i class="bi bi-check-circle"></i> ${isSale ? 'Process Sale' : 'Process Rental'} — ₱${fmtTotal}`
                : `<i class="bi bi-check-circle"></i> ${isSale ? 'Process Sale' : 'Process Rental'}`;
        }

        // Mobile sticky bar
        const stickyId    = isSale ? 'stickyTotal' : 'rentalStickyTotal';
        const stickyBtnId = isSale ? 'stickyCheckoutBtn' : 'rentalStickyBtn';
        const stickyEl    = document.getElementById(stickyId);
        const stickyBtn   = document.getElementById(stickyBtnId);

        if (stickyEl)  stickyEl.textContent = fmtTotal;
        if (stickyBtn) stickyBtn.disabled   = !hasItems;
    }

    // Highlight card on qty change
    qtyInputs.forEach(input => {
        input.addEventListener('input', () => {
            const card = input.closest(cardClass);
            const qty  = parseInt(input.value) || 0;
            card.classList.toggle(borderClass, qty > 0);
            card.classList.toggle('shadow',     qty > 0);
            updateCart();
        });
    });

    // Confirm before submit (via shared confirmation modal)
    const form = document.getElementById(formId);
    form?.addEventListener('submit', e => {
        // Rental: require renter name
        if (!isSale) {
            const nameField = document.getElementById('id_renter_name');
            if (nameField && !nameField.value.trim()) {
                e.preventDefault();
                nameField.focus();
                return;
            }
        }
        const total = grandTotal?.textContent || '0.00';
        const label = isSale ? 'sale' : 'rental';
        e.preventDefault();

        window.ptConfirm?.({
            title:        `Process ${label}`,
            body:         `Process ${label} for ₱${total}?`,
            confirmLabel: 'Process',
            confirmClass: isSale ? 'btn-success' : 'btn-warning',
            onConfirm:    () => form.submit(),
        });
    });

});