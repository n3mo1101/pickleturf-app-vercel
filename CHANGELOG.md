# Changelog

## 2026-11-05 — Compact booking time summaries

### Changed
- Non-consecutive multi-slot bookings now show only their first contiguous time range in booking tables
- Added an `NC` badge beside the slot count to flag non-consecutive selections
- Full time summaries are retained for transaction descriptions and cancellation confirmations

## 2026-11-04 — Multi-slot reservations

### Added
- `BookingSlot` model with a partial unique constraint on active court/date/time slots
- Data migration that backfills one `BookingSlot` per existing `Booking`
- One `Transaction` per reservation, covering every selected time slot
- Per-slot PayMongo checkout line items for multi-slot reservations
- Expandable time-slot summaries in customer, staff, and admin booking tables
- `Slots` column in the transactions CSV export

### Changed
- `Booking` now represents a reservation header with summary start/end times and total price
- Availability, conflict checks, and slot generation now query `BookingSlot`
- Multi-slot bookings are created atomically; one unavailable slot rejects the whole reservation
- Admin status updates, cancellations, and auto-completion now operate on the whole reservation
- Booking and transaction totals remain per reservation; `total bookings` now counts reservations rather than slots

### Fixed
- Online payment for multi-slot bookings now covers every selected slot instead of only the first
- Cancelling an unpaid online booking waives its transaction instead of marking it refunded
- Admin mark-paid confirms a pending booking and completes it only after the last slot ends

### Removed
- Per-slot booking creation and the “pay the remaining slots later” flow

## 2026-11-02 — Admin form modals

### Added
- Shared form modal loader with partial rendering for booking status, stock adjustment, and category forms
- Confirmation modals for open play approve, reject, and manual participant actions

### Changed
- Admin and staff booking status updates now open in a modal and return to the originating list
- Inventory stock adjustments and category create/edit now open in modals while keeping full-page fallbacks
- Open play participant row actions now show the participant and session names before submitting

## 2026-11-02 — UI/UX bug fixes

### Added
- Version control conventions in `AGENTS.md` for commit messages and `CHANGELOG.md`

### Changed
- File input chooser restyled as an inset pill with even spacing and a separate filename area

### Fixed
- New customer signups redirect to the customer home instead of the admin dashboard, removing the duplicate "Access denied" toast
- Floating action button no longer blocks clicks on table rows underneath it

## 2026-10-09 — Export CSV modal

### Added
- Reusable export modal (type + date range picker with "All records" toggle), shared from base layout on the dashboard and transactions pages
- Daily revenue (`Date, Total`) and monthly revenue (`Month, Total`) CSV reports over the same paid/pending data as the dashboard
- Export coverage tests (auth, type/range validation, CSV shape)

### Changed
- Dashboard header dropdown and transactions-page direct link replaced by a single modal trigger button
- One unified `dashboard:export_csv` endpoint (`?type=&start=&end=`); transactions export now supports date ranges and range-stamped filenames

### Removed
- Raw Bookings and Rentals CSV exports and their `export/bookings`, `export/rentals` routes

## 2026-10-09 — Analytics dashboard & filters

### Added
- Daily revenue range toggle (7D / 14D / 30D, default 30D) — seamless client-side switching, no reload
- Hero revenue split (Bookings & Open Play vs Products) with a grey last-transaction pill
- 3-dot overflow menu in inventory admin header (Categories, Shop view)

### Changed
- Chart rows reordered: today's bookings + recent transactions, daily revenue + upcoming open play (daily widened), monthly revenue + revenue by type
- Stat cards: larger values, icon + title on one row, stacked left-aligned layout, 4px navy accent border (lighter navy in dark mode)
- Search/filter toolbars standardized (38px controls) across bookings, sessions, inventory, rentals, POS, rent POS, shop, transactions, and availability
- Daily revenue area fill yellow → theme-aware navy; service worker static caching moved to stale-while-revalidate (v3) so style updates reach clients

### Fixed
- Clear buttons removed from open play admin, POS, and rental POS forms; outline eraser style on the remaining filter rows
- Availability date field label removed in favor of an icon-only, `aria-label`ed field

## 2026-10-09 — UI/UX refinement

### Added
- Availability page slot states (available / reserved / unavailable / past) with legend
- Dashboard KPI hero/stack grid and theme-aware charts: daily revenue, revenue by type, monthly revenue
- Profile page stats (bookings, total spent, courts played), appearance toggle, account & security rows
- Live password rules on auth forms (8+ chars, not only numbers, match) — shown only while failing
- Mobile POS sticky checkout bars; mobile card mode for data tables

### Changed
- Rebuilt CSS design system (base, components, pages, dark mode)
- De-cluttered tables: 3-dot row action menus, muted uppercase headers, hidden empty action cells
- Standardized CTAs: navy primary, yellow accent, green reserved for success
- Sentence-case titles and buttons; plain card headers without colored banners or icons
- Theme-aware dashboard charts driven by `pt:themechange`; sidebar/nav label cleanup

### Fixed
- Stray quote in announcements admin list; confirm-modal default title
- Dark-mode contrast issues (yellow-on-white text, sticky totals)
- Required-field `*` markers removed via crispy field override (`templates/bootstrap5/`)

### Removed
- Court utilization and bookings-by-weekday dashboard widgets
- Dead `static/css/main/main.css`; emoji/decorative icons in headings; em-dash separators in titles (now `·`)
