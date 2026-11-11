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

Management commands: `seed_courts`, `update_booking_statuses`.

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
