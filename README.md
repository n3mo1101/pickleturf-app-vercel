# PickleTurf App

A web-based management system for a single pickleball facility.
Built to handle court bookings, open play sessions, equipment sales and rentals,
inventory management, and business analytics — all in one place.

---

## 🚀 Features

### 📱 Customer
- Register and log in via email/password or Google OAuth
- Book courts by selecting available time slots (multi-slot, hourly pricing)
- Join open play sessions and track approval status
- View booking history with summary and pagination
- Browse the equipment shop
- View active announcements on the home page

### 🧑‍💻 Admin / Staff
- Dashboard with revenue charts, booking stats, and court utilization
- Manage court bookings — create, confirm, cancel, and track status
- Create and manage open play sessions, approve or reject participants
- Point-of-sale interface for recording equipment purchases
- Rental POS for processing equipment rentals
- Full inventory management — items, categories, stock adjustments
- Transaction history with filters, date range, and CSV export
- Announcement system with live preview and banner display
- Role-based access control (Admin, Staff, Customer)

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 4.2 (Python) |
| Database | PostgreSQL |
| Authentication | django-allauth (email + Google OAuth) |
| Frontend | Django Templates, Bootstrap 5, Chart.js |
| Styling | Custom CSS (Navy + Yellow theme, dark mode) |
| Static Files | WhiteNoise |
| Media Files | Cloudinary |
| Server | Gunicorn |
| Hosting | Render |

---

## 📂 Project Structure

```
pickleball_app/
├── accounts/         # Custom user model, auth adapters, decorators
├── bookings/         # Court booking system, availability, services
├── courts/           # Court model and seeding
├── openplay/         # Open play sessions and participant management
├── inventory/        # Items, categories, stock, POS, rental POS
├── transactions/     # Transaction records and history
├── announcements/    # Announcement CRUD and banner display
├── dashboard/        # Analytics, charts, and CSV exports
├── core/             # Landing page and customer home
├── config/           # Django settings and URL configuration
├── static/           # CSS, JS, and image assets
└── templates/        # All HTML templates
```

---

## 🔧 Setup (Local Development)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/pickleturf.git
cd pickleturf

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your local database and credentials

# 5. Create the PostgreSQL database
psql -U postgres -c "CREATE DATABASE pickleball_db;"

# 6. Run migrations
python manage.py migrate

# 7. Seed initial courts
python manage.py seed_courts

# 8. Create a superuser
python manage.py createsuperuser

# 9. Run the development server
python manage.py runserver
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest -v

# Run a specific app
pytest bookings/tests.py -v

# Run a specific test
pytest bookings/tests.py::BookingServiceTests::test_duplicate_booking_raises_error
```

---

## License

This project is for private use. All rights reserved.