// ── PickleTurf export modal ────────────────────────────────────────────────────
// Trigger buttons open #ptExportModal via Bootstrap data attributes:
//   data-export-url   (export endpoint — required)
//   data-export-type  (transactions | daily | monthly — optional preselect)
//
// On submit: build `url?type=&start=&end=` (dates only when "All records"
// is off), trigger the download via location.assign, then close the modal.

(function () {
    const modalEl = document.getElementById('ptExportModal');
    if (!modalEl) return;

    const form    = document.getElementById('ptExportForm');
    const typeEl  = document.getElementById('ptExportType');
    const allEl   = document.getElementById('ptExportAll');
    const startEl = document.getElementById('ptExportStart');
    const endEl   = document.getElementById('ptExportEnd');

    let exportUrl = '';

    function syncDates() {
        const all = allEl.checked;
        startEl.disabled = all;
        endEl.disabled   = all;
        startEl.required = !all;
        endEl.required   = !all;
        if (all) {
            startEl.value = '';
            endEl.value   = '';
        }
    }

    modalEl.addEventListener('show.bs.modal', event => {
        const trigger = event.relatedTarget;
        exportUrl = trigger?.dataset.exportUrl || '';
        const preset = trigger?.dataset.exportType;
        if (preset && [...typeEl.options].some(o => o.value === preset)) {
            typeEl.value = preset;
        }
        allEl.checked = true;
        syncDates();
    });

    allEl.addEventListener('change', syncDates);

    form.addEventListener('submit', event => {
        event.preventDefault();
        if (!form.checkValidity() || !exportUrl) {
            form.reportValidity();
            return;
        }
        const params = new URLSearchParams({ type: typeEl.value });
        if (!allEl.checked) {
            params.set('start', startEl.value);
            params.set('end', endEl.value);
        }
        bootstrap.Modal.getInstance(modalEl)?.hide();
        window.location.assign(`${exportUrl}?${params}`);
    });
})();
