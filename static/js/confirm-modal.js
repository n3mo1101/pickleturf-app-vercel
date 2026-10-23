/* ============================================================
   PICKLETURF — CONFIRM MODAL
   Shared Bootstrap confirmation modal.
   - Programmatic: window.ptConfirm({title, body, details,
     confirmLabel, confirmClass, onConfirm})
   - Declarative:  <form data-pt-confirm
                        data-pt-confirm-title=...
                        data-pt-confirm-body=...
                        data-pt-confirm-label=...
                        data-pt-confirm-class=...
                        data-pt-confirm-details='[{"label":"...","value":"..."}]'>
                   <a href="..." data-pt-confirm ...> → GET nav on confirm
   ============================================================ */
(function () {
    const modalEl = document.getElementById('ptConfirmModal');
    if (!modalEl) return;

    const modal     = new bootstrap.Modal(modalEl);
    const titleEl   = document.getElementById('ptConfirmTitle');
    const bodyEl    = document.getElementById('ptConfirmBody');
    const detailsEl = document.getElementById('ptConfirmDetails');
    const okBtn     = document.getElementById('ptConfirmOk');
    const okLabelEl = document.getElementById('ptConfirmOkLabel');

    let pendingForm = null;
    let onConfirmCb = null;
    let bypass      = false;

    function readOptions(dataset) {
        let details = [];
        if (dataset.ptConfirmDetails) {
            try {
                details = JSON.parse(dataset.ptConfirmDetails) || [];
            } catch (e) {
                details = [];
            }
        }
        return {
            title:        dataset.ptConfirmTitle || 'Are you sure?',
            body:         dataset.ptConfirmBody  || '',
            details:      details,
            confirmLabel: dataset.ptConfirmLabel || 'Confirm',
            confirmClass: dataset.ptConfirmClass || 'btn-primary',
        };
    }

    function openConfirm(options) {
        titleEl.textContent = options.title || 'Are you sure?';
        bodyEl.textContent  = options.body  || '';
        detailsEl.innerHTML = '';

        if (options.details && options.details.length) {
            options.details.forEach(function (d) {
                const li = document.createElement('li');
                li.className = 'list-group-item py-2 small';
                li.innerHTML = '<strong>' + d.label + ':</strong> ' + d.value;
                detailsEl.appendChild(li);
            });
            detailsEl.style.display = '';
        } else {
            detailsEl.style.display = 'none';
        }

        okLabelEl.textContent = options.confirmLabel || 'Confirm';
        okBtn.className       = 'btn ' + (options.confirmClass || 'btn-primary');

        pendingForm = options.form     || null;
        onConfirmCb = options.onConfirm || null;

        modal.show();
    }

    okBtn.addEventListener('click', function () {
        modal.hide();
        if (pendingForm) {
            bypass = true;
            setTimeout(() => { bypass = false; }, 0);
            pendingForm.submit();
        } else if (onConfirmCb) {
            onConfirmCb();
        }
        pendingForm = null;
        onConfirmCb = null;
    });

    modalEl.addEventListener('hidden.bs.modal', function () {
        pendingForm = null;
        onConfirmCb = null;
    });

    // Declarative: <form data-pt-confirm ...>
    document.addEventListener('submit', function (e) {
        if (bypass) { bypass = false; return; }
        const form = e.target;
        if (!(form instanceof HTMLElement) || !form.hasAttribute('data-pt-confirm')) return;
        e.preventDefault();
        const opts = readOptions(form.dataset);
        opts.form = form;
        openConfirm(opts);
    }, true);

    // Declarative: <a data-pt-confirm ...>
    document.addEventListener('click', function (e) {
        const a = e.target.closest('a[data-pt-confirm]');
        if (!a) return;
        e.preventDefault();
        const opts = readOptions(a.dataset);
        opts.onConfirm = function () {
            window.location.href = a.href;
        };
        openConfirm(opts);
    });

    window.ptConfirm = openConfirm;
})();