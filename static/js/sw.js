/* ============================================================
   PICKLETURF SERVICE WORKER
   Cache-first for static assets, network-first for pages
   ============================================================ */

const CACHE_VERSION  = 'pickleturf-v3';
const STATIC_CACHE   = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE  = `${CACHE_VERSION}-dynamic`;

// ── Assets to pre-cache on install ────────────────────────────
const STATIC_ASSETS = [
    '/',
    '/bookings/',
    '/openplay/',
    '/inventory/shop/',
    '/static/css/base.css',
    '/static/css/components.css',
    '/static/css/pages.css',
    '/static/css/dark-mode.css',
    '/static/js/main.js',
    '/static/js/pos.js',
    '/static/img/logo.png',
    '/static/img/logo-256.png',
    '/offline/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css',
    'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap',
];

// ── Pages to cache dynamically when visited ────────────────────
const CACHEABLE_PAGES = [
    '/',
    '/bookings/',
    '/bookings/my/',
    '/openplay/',
    '/inventory/shop/',
    '/dashboard/',
    '/transactions/',
];

// ── Install ────────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => cache.addAll(STATIC_ASSETS))
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
                                   key !== STATIC_CACHE &&
                                   key !== DYNAMIC_CACHE)
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

    // Skip admin and API calls — always network
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

    // ── HTML pages: network-first, fall back to cache ──────────
    if (request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // Cache successful page responses
                    if (
                        response.ok &&
                        CACHEABLE_PAGES.some(p => url.pathname === p ||
                                                   url.pathname.startsWith(p))
                    ) {
                        const clone = response.clone();
                        caches.open(DYNAMIC_CACHE)
                            .then(cache => cache.put(request, clone));
                    }
                    return response;
                })
                .catch(() =>
                    // Network failed — try cache, else show offline page
                    caches.match(request).then(cached =>
                        cached || caches.match('/offline/')
                    )
                )
        );
        return;
    }

    // ── Everything else: network-first ─────────────────────────
    event.respondWith(
        fetch(request).catch(() => caches.match(request))
    );
});