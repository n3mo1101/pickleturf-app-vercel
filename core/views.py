from datetime import date
from django.shortcuts import render
from django.http import FileResponse
import os


def home_view(request):
    """Landing for guests, customer home for authenticated users."""
    if request.user.is_authenticated:
        return _customer_home(request)
    return render(request, 'core/landing.html')


def _customer_home(request):
    from bookings.models import Booking
    from bookings.services import auto_update_booking_statuses
    from openplay.models import OpenPlaySession
    from announcements.models import Announcement

    today = date.today()

    # Auto-update stale bookings on every home load
    auto_update_booking_statuses()

    upcoming_bookings = (
        Booking.objects
        .filter(
            user=request.user,
            date__gte=today,
            status__in=['confirmed', 'pending']
        )
        .select_related('court')
        .order_by('date', 'start_time')[:6]
    )

    todays_sessions = (
        OpenPlaySession.objects
        .filter(
            date=today,
            status__in=['open', 'full']
        )
        .order_by('start_time')
    )

    announcements = Announcement.objects.filter(
        is_active=True
    ).order_by('-created_at')

    return render(request, 'core/customer_home.html', {
        'upcoming_bookings': upcoming_bookings,
        'todays_sessions':   todays_sessions,
        'announcements':     announcements,
        'today':             today,
    })


def offline_view(request):
    return render(request, 'core/offline.html')


def service_worker_view(request):
    """Serve SW from root scope so it can intercept all requests."""
    from django.conf import settings
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'sw.js')
    response = FileResponse(
        open(sw_path, 'rb'),
        content_type='application/javascript'
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response