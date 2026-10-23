# Changelog

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
