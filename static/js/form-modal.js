/* ============================================================
   PICKLETURF — FORM MODAL
   Loads server-rendered form partials into #ptFormModal.

   Triggers:
     <a href="..." data-pt-form-modal>...</a>
     <button data-pt-form-modal="...">...</button>

   The GET request adds ?modal=1 and the POST request sends
   X-Requested-With: fetch so views can return partials.
   ============================================================ */
(function () {
    const modalEl = document.getElementById('ptFormModal');
    if (!modalEl) return;

    const dialogEl = document.getElementById('ptFormModalDialog');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    let controller = null;

    function loadingContent() {
        return `
            <div class="modal-content">
                <div class="modal-body text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading…</span>
                    </div>
                </div>
            </div>`;
    }

    function errorContent(message) {
        return `
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="ptFormModalLabel">Unable to load form</h5>
                    <button type="button" class="btn-close"
                            data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-danger mb-0">${message}</div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-outline-secondary"
                            data-bs-dismiss="modal">Close</button>
                </div>
            </div>`;
    }

    function showContent(html) {
        dialogEl.innerHTML = html;
        const firstField = dialogEl.querySelector(
            'input:not([type="hidden"]):not([type="submit"]), select, textarea'
        );
        if (firstField) firstField.focus();
    }

    function modalUrl(url) {
        const parsed = new URL(url, window.location.origin);
        parsed.searchParams.set('modal', '1');
        return parsed.toString();
    }

    async function loadForm(url) {
        if (controller) controller.abort();
        controller = new AbortController();

        dialogEl.innerHTML = loadingContent();
        modal.show();

        try {
            const response = await fetch(modalUrl(url), {
                headers: { 'X-Requested-With': 'fetch' },
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error('Request failed');
            }
            showContent(await response.text());
        } catch (error) {
            if (error.name === 'AbortError') return;
            showContent(errorContent('The form could not be loaded. Please try again.'));
        }
    }

    document.addEventListener('click', function (event) {
        const trigger = event.target.closest('[data-pt-form-modal]');
        if (!trigger) return;

        event.preventDefault();
        const url = trigger.dataset.ptFormModal || trigger.getAttribute('href');
        if (url) loadForm(url);
    });

    modalEl.addEventListener('submit', async function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        event.preventDefault();

        const submitButtons = form.querySelectorAll(
            'button[type="submit"], input[type="submit"]'
        );
        submitButtons.forEach(button => { button.disabled = true; });

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'fetch' },
            });

            if (response.redirected) {
                modal.hide();
                window.location.assign(response.url);
                return;
            }

            if (!response.ok) {
                throw new Error('Request failed');
            }

            showContent(await response.text());
        } catch (error) {
            const alert = document.createElement('div');
            alert.className = 'alert alert-danger m-3 mb-0';
            alert.textContent = 'Could not save changes. Please try again.';
            form.prepend(alert);
        } finally {
            submitButtons.forEach(button => { button.disabled = false; });
        }
    });

    modalEl.addEventListener('hidden.bs.modal', function () {
        if (controller) {
            controller.abort();
            controller = null;
        }
        dialogEl.innerHTML = '';
    });
})();
