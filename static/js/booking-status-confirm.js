/* ============================================================
   PICKLETURF — BOOKING STATUS CONFIRM
   Asks for confirmation when an admin sets a booking to
   Cancelled or Completed. The form works without confirmation
   for any other status change.

   Works with both the form modal partial and the standalone
   admin_booking_status.html page.
   ============================================================ */
(function () {
    var CONFIRM_STATUSES = ['cancelled', 'completed'];

    function sync(form) {
        var select = form.querySelector('select[name="status"]');
        if (!select) return;

        var value = select.value;
        var id = form.dataset.bookingId || '';
        var label = form.dataset.bookingLabel || 'this booking';

        if (CONFIRM_STATUSES.indexOf(value) === -1) {
            form.removeAttribute('data-pt-confirm');
            ['data-pt-confirm-title', 'data-pt-confirm-body',
             'data-pt-confirm-label', 'data-pt-confirm-class']
                .forEach(function (attr) { form.removeAttribute(attr); });
            return;
        }

        if (value === 'cancelled') {
            form.dataset.ptConfirmTitle = 'Cancel booking';
            form.dataset.ptConfirmBody =
                'Cancel booking #' + id + ' for ' + label + '? ' +
                'The slot will be released and any collected payment ' +
                'marked for refund.';
            form.dataset.ptConfirmLabel = 'Cancel booking';
            form.dataset.ptConfirmClass = 'btn-danger';
        } else {
            form.dataset.ptConfirmTitle = 'Complete booking';
            form.dataset.ptConfirmBody =
                'Mark booking #' + id + ' for ' + label + ' as completed? ' +
                'Payment status is recorded separately and will not change.';
            form.dataset.ptConfirmLabel = 'Complete booking';
            form.dataset.ptConfirmClass = 'btn-success';
        }
    }

    function findForm(target) {
        var select = target.closest('select[name="status"]');
        if (!select) return null;
        return select.closest('form');
    }

    document.addEventListener('change', function (event) {
        var form = findForm(event.target);
        if (form) sync(form);
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-booking-status-form]')
            .forEach(sync);
    });
})();
