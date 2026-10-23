from django.core.management.base import BaseCommand
from bookings.services import auto_update_booking_statuses


class Command(BaseCommand):
    help = 'Auto-complete or auto-cancel bookings based on time'

    def handle(self, *args, **kwargs):
        auto_update_booking_statuses()
        self.stdout.write(self.style.SUCCESS(
            'Booking statuses updated successfully.'
        ))