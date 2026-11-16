# PickleTurf

A web-based management system for a single pickleball facility — court reservations,
open play, equipment sales and rentals, inventory, online payments, and analytics.

---

## Features

### Customer
- Sign up / log in with email (or Google / Facebook) via `django-allauth`
- Reserve one or more hourly court slots with live price breakdown
- Pay online via PayMongo (GCash) or choose pay-on-site
- Join open play sessions and track approval status
- View booking history, browse the shop, read announcements
- Light and dark theme

### Admin / Staff
- Dashboard KPIs, revenue charts, and court utilization
- Reservations with `Reserved` / `Completed` / `Missed` / `Cancelled` statuses
- Search and filter by status, court, and date; manual `Mark paid`
- Open play creation, participant approval, and walk-in registration
- POS for equipment sales and equipment rentals
- Inventory items (`For Sale` or `For Rent`), stock adjustments, sale/rental history
- Transaction history with filters and CSV export
- Announcement CRUD with live preview
- Role-based access: Admin, Staff, Customer

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0 (Python 3.12) |
| Database | PostgreSQL (Supabase) via `DATABASE_URL` |
| Auth | django-allauth (email / Google / Facebook) |
| Payments | PayMongo (GCash), webhook-verified |
| Frontend | Django templates, Bootstrap 5, crispy-bootstrap5, Chart.js |
| Static files | WhiteNoise |
| Media | Cloudinary |
| Server | Gunicorn |
| Hosting | Vercel (cron) — Railway configs also included |

---

## Project Structure

```
pickleturf-app-vercel/
├── accounts/       # Custom user model, roles, auth adapters
├── bookings/       # Reservations, multi-slot availability, status cron
├── courts/         # Court model and seed_courts command
├── openplay/       # Open play sessions and participants
├── inventory/      # Items, categories, stock, sales POS, rental POS
├── transactions/   # Transaction records and history
├── announcements/  # Announcement CRUD and site banner
├── dashboard/      # Analytics, charts, CSV exports
├── core/           # Landing page and customer home
├── config/         # Django settings and URL configuration
├── static/         # CSS, JS, images
└── templates/      # All HTML templates
```

Management commands: `seed_courts`, `update_booking_statuses`, `mark_emails_verified`, `preview_emails`.

---

## Setup (Local)

Copy `.env.example` to `.env` and fill in the values before running migrations.

```bash
git clone <repo-url> && cd pickleturf-app-vercel
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt

cp .env.example .env
python manage.py migrate
python manage.py seed_courts
python manage.py createsuperuser
python manage.py runserver
```

---

## Email Verification

Signups must confirm their email before they can sign in. Google/Facebook
sign-ins skip this, because the provider has already verified the address.

| Variable | Value |
|---|---|
| `ACCOUNT_EMAIL_VERIFICATION` | `mandatory` (`optional` to warn only, `none` to disable) |
| `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS` | `1` |
| `PASSWORD_RESET_TIMEOUT` | `86400` (seconds) |
| `EMAIL_BACKEND` | blank = console in `DEBUG`, SMTP otherwise |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` | `smtp.gmail.com` / `587` / `True` |
| `EMAIL_HOST_USER` | Gmail address that sends the mail |
| `EMAIL_HOST_PASSWORD` | 16-character Google App Password |
| `DEFAULT_FROM_EMAIL` | `PickleTurf <same-gmail-address>` |
| `ACCOUNT_EMAIL_NOTIFICATIONS` | `True` in `config/settings.py` (security notices are off by default in allauth) |

Local development prints the confirmation link to the `runserver` terminal
when `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.

For Gmail, enable 2-Step Verification, create an App Password at
<https://myaccount.google.com/apppasswords>, and use that instead of the
account password. Gmail caps sends at roughly 500 recipients/day.

Before enabling `mandatory` on a live site, grandfather existing accounts once
against the production database:

```bash
python manage.py mark_emails_verified --dry-run
python manage.py mark_emails_verified
```

Verification emails are throttled to one per address every 3 minutes, and
unverified users get a fresh link whenever they try to sign in.

---

## Transactional Email Design

Every customer-facing email (confirmation, password reset, account-exists,
unknown-account, and the five security notices) is a branded PickleTurf HTML
email with a plain-text fallback.

- Templates live in `templates/account/email/`. Each has a `_message.html`
  design and a matching `.txt` fallback; the shared shell is
  `base_email.html` with partials for the button, fallback link, and security
  note.
- Styling is inline CSS only (no `<style>` blocks except the Outlook font
  shim), forming a 600px table layout on a navy `#1B2A4A` header with a
  `#F5C518` accent.
- Subjects are set per template, so `ACCOUNT_EMAIL_SUBJECT_PREFIX` is empty and
  no `[PickleTurf]` prefix is added.
- The `Site` record must say `PickleTurf` — the footer prints
  `current_site.domain`.

Preview the whole set in a browser (output goes to `_preview/`, gitignored):

```bash
python manage.py preview_emails          # writes _preview/index.html
python manage.py preview_emails --open   # and opens it
```

---

## Tests

```bash
pytest -v                                        # all tests
pytest bookings/tests.py -v                      # one app
pytest bookings/tests.py::BookingServiceTests -v # one class
```

Config lives in `pytest.ini` (`DJANGO_SETTINGS_MODULE=config.settings`).

---

## Deployment (Vercel)

- Set the required environment variables (see `.env.example`) in the Vercel project with `DEBUG=False`
- `vercel.json` runs the cron `/bookings/cron/update-statuses/` daily to expire past reservations and sessions
- Static files are served by WhiteNoise; uploaded media goes to Cloudinary
- `railway.toml` / `nixpacks.toml` / `Procfile` remain for a Railway deploy (`gunicorn config.wsgi`)

---

## License

Private use. All rights reserved.
