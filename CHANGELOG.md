# Changelog

## 2026-11-10 — Open play auto-completion

### Changed
- Open play sessions automatically move to `Completed` once their end time passes
- Status refresh runs on open play page loads, the dashboard, the customer home, and the daily cron
- Approving or adding participants on a completed or cancelled session is blocked
- Late online payments for an ended session are automatically refunded

## 2026-11-10 — Reservation statuses and paid-only revenue

### Added
- `Missed` booking status for unpaid reservations whose slot has passed
- `Mark paid` action in booking row menus, including recovery for missed bookings with a waived charge
- Search, status, court, and date filters on the staff bookings list
- Customer name/email search on the All bookings list
- Date filter on the open play manage page
- Shared `mark_transaction_paid` service for manual payment collection
- Confirmation prompt when a booking status changes to `Cancelled` or `Completed`

### Changed
- Booking statuses are now `Reserved`, `Completed`, `Missed`, and `Cancelled`; every new booking starts as `Reserved`
- Revenue on the dashboard, charts, revenue CSV exports, customer totals, and the transactions tile counts paid transactions only
- Completing a booking no longer marks its transaction paid
- Auto-status refresh completes paid past bookings and marks unpaid ones `Missed` with the charge waived
- Staff booking creation includes a checked-by-default `Mark as paid` option
- Open play approvals and manual walk-in adds record a paid transaction; PayMongo payments keep their provider
- Open play join flow shows `Request to join`, a waiting state, and a `Pay now` option
- Staff bookings list now matches the All bookings layout and actions

### Fixed
- Date and time picker icons are visible in dark mode
- Booking confirmation copy and submit label now use reservation wording

### Removed
- `Pending` and `Confirmed` booking statuses, migrated to `Reserved`
- Notes input from the customer and staff booking forms

## 2026-11-08 — Interface refinements

### Changed
- Open play manage page actions (`Edit`, `Complete`, `Cancel`) are now in a 3-dots dropdown
- Inventory rows use the default background and hover instead of yellow/red stock tints; stock counts remain color-coded
- Shop grid displays two items per row on phones, three on tablets, and four on desktop
- Clicking an `Available` slot on the availability grid opens the booking form with that slot pre-checked and the price summary updated
- Shop cards use compact image and text sizing below `576px`
- Prices across shop, POS, availability, booking form, dashboard, and transactions use the theme text color (navy in light mode, near-white in dark mode)
- Booking form and open play detail icons use the same adaptive text color instead of mixed status colors

## 2026-11-05 — Dashboard KPI and chart refresh

### Added
- 7-day revenue sparkline in the daily revenue KPI card
- Month-over-month change, pending bookings, and longest active rental badges on KPI cards
- Scrollable upcoming-bookings card that only lists today's bookings which have not ended yet

### Changed
- `Today's bookings` KPI shows completed / total, with pending included in the total
- Recent transactions and upcoming bookings now share row 1 (`col-lg-9` / `col-lg-3`)
- Daily revenue chart spans the full row; upcoming open play is hidden
- Monthly revenue bars use the primary navy chart color
- KPI card icons are hidden so card values stand out
- Sparkline is constrained to a fixed area so revenue spikes cannot resize the hero card
- Hero revenue divider sits below the content instead of being pinned to the card bottom

### Removed
- Legacy today's bookings list and its `View all` footer

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
