/* ============================================================
   PICKLETURF SERVICE WORKER
   Stale-while-revalidate for static assets, network-only for pages
   ============================================================ */

const CACHE_VERSION  = 'pickleturf-v5';
const STATIC_CACHE   = `${CACHE_VERSION}-static`;

// ── Assets to pre-cache on install ────────────────────────────
// Static assets and the generic offline page only. HTML pages are
// never pre-cached: they differ per user and per session.
const STATIC_ASSETS = [
    '/static/css/base.css',
    '/static/css/components.css',
    '/static/css/pages.css',
    '/static/css/dark-mode.css',
    '/static/js/main.js',
    '/static/js/form-modal.js',
    '/static/js/pos.js',
    '/static/img/logo.png',
    '/static/img/logo-256.png',
    '/offline/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css',
    'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap',
];

// ── Install ────────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => Promise.all(
                // Cache each asset independently so a single failure
                // (offline, 404, CDN hiccup) cannot abort installation.
                STATIC_ASSETS.map(url =>
                    cache.add(new Request(url, { cache: 'reload' }))
                        .catch(() => {})
                )
            ))
            .then(() => self.skipWaiting())
    );
});

// ── Activate — clean up old caches ────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(key => key.startsWith('pickleturf-') &&
                                   key !== STATIC_CACHE)
                    .map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

// ── Fetch Strategy ─────────────────────────────────────────────
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET and browser extensions
    if (request.method !== 'GET') return;
    if (!url.protocol.startsWith('http')) return;

    // Skip admin and auth flows — always network
    if (url.pathname.startsWith('/admin/')) return;
    if (url.pathname.startsWith('/accounts/')) return;

    // ── Static assets: stale-while-revalidate ─────────────────
    if (
        url.pathname.startsWith('/static/') ||
        url.hostname.includes('jsdelivr.net') ||
        url.hostname.includes('fonts.googleapis.com') ||
        url.hostname.includes('fonts.gstatic.com')
    ) {
        event.respondWith(
            caches.match(request).then(cached => {
                const refresh = fetch(request).then(response => {
                    if (response && (response.ok || response.type === 'opaque')) {
                        const clone = response.clone();
                        caches.open(STATIC_CACHE)
                            .then(cache => cache.put(request, clone));
                    }
                    return response;
                });

                if (cached) {
                    refresh.catch(() => {});
                    return cached;
                }
                return refresh;
            })
        );
        return;
    }

    // ── HTML pages: network-only, offline fallback ────────────
    // Pages are NEVER written to a cache. Responses can be
    // personalised (dashboard, my bookings, transactions) and a
    // shared device would otherwise show one user's data to the
    // next person after logout.
    if (request.mode === 'navigate' ||
        request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(
            fetch(request).catch(() => caches.match('/offline/'))
        );
        return;
    }

    // ── Everything else: network-first ─────────────────────────
    event.respondWith(
        fetch(request).catch(() => caches.match(request))
    );
});
