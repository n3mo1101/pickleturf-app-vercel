/* ============================================================
   PICKLETURF — MAIN JS
   Sidebar · Dark Mode · FAB · PWA Support 
   ============================================================ */

/* ── Theme ───────────────────────────────────────────────────── */
(function () {
    const saved = localStorage.getItem('pt-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
    const html    = document.documentElement;
    const current = html.getAttribute('data-theme') || 'light';
    const next    = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('pt-theme', next);
    updateThemeBtn(next);
    document.dispatchEvent(new CustomEvent('pt:themechange', { detail: { theme: next } }));
}

function updateThemeBtn(theme) {
    const isDark = theme === 'dark';
    const icon   = isDark ? 'bi-sun-fill' : 'bi-moon-fill';

    // Sidebar footer button (icon + label)
    const sidebarBtn = document.getElementById('themeToggleBtn');
    if (sidebarBtn) {
        sidebarBtn.innerHTML =
            `<i class="bi ${icon} nav-icon"></i>` +
            `<span>${isDark ? 'Light Mode' : 'Dark Mode'}</span>`;
    }

    // Mobile topbar button (icon only)
    const topbarBtn = document.getElementById('topbarThemeBtn');
    if (topbarBtn) {
        topbarBtn.innerHTML = `<i class="bi ${icon}"></i>`;
    }

    // Profile page appearance row (icon + label)
    const profileBtn = document.getElementById('profileThemeBtn');
    if (profileBtn) {
        profileBtn.innerHTML =
            `<i class="bi ${icon}"></i> ${isDark ? 'Light mode' : 'Dark mode'}`;
    }
}

/* ── Sidebar ─────────────────────────────────────────────────── */
function openSidebar() {
    document.getElementById('ptSidebar')?.classList.add('show');
    document.getElementById('ptOverlay')?.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function closeSidebar() {
    document.getElementById('ptSidebar')?.classList.remove('show');
    document.getElementById('ptOverlay')?.classList.remove('show');
    document.body.style.overflow = '';
}

/* ── FAB ─────────────────────────────────────────────────────── */
function toggleFAB() {
    const fab = document.getElementById('ptFAB');
    if (!fab) return;
    fab.classList.toggle('open');
}

// Close FAB when clicking outside
document.addEventListener('click', function (e) {
    const fab = document.getElementById('ptFAB');
    if (fab && !fab.contains(e.target)) {
        fab.classList.remove('open');
    }
});

/* ── Init ────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
    // Set theme button state
    const theme = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeBtn(theme);

    // Auto-expand sidebar submenu if active
    document.querySelectorAll('.pt-submenu-link.active').forEach(link => {
        const submenu = link.closest('.pt-submenu');
        if (submenu) {
            submenu.classList.add('show');
            const toggle = document.querySelector(
                `[data-bs-target="#${submenu.id}"]`
            );
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
        }
    });

    // Close sidebar on overlay click
    document.getElementById('ptOverlay')
        ?.addEventListener('click', closeSidebar);

    // Show flash message toasts (auto-dismiss via data-bs-delay)
    document.querySelectorAll('#ptToastContainer .toast').forEach(toast => {
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
    });
});

/* ── PWA Install ─────────────────────────────────────────────── */
let deferredInstallPrompt = null;

// Capture the install prompt event
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;

    // Show the install button in sidebar
    const installBtn = document.getElementById('pwaInstallBtn');
    if (installBtn) {
        installBtn.style.display = 'flex';
    }
});

function installPWA() {
    if (!deferredInstallPrompt) return;

    deferredInstallPrompt.prompt();

    deferredInstallPrompt.userChoice.then(result => {
        if (result.outcome === 'accepted') {
            // Hide button after install
            const installBtn = document.getElementById('pwaInstallBtn');
            if (installBtn) installBtn.style.display = 'none';
        }
        deferredInstallPrompt = null;
    });
}

// Hide install button if already installed
window.addEventListener('appinstalled', () => {
    const installBtn = document.getElementById('pwaInstallBtn');
    if (installBtn) installBtn.style.display = 'none';
    deferredInstallPrompt = null;
});