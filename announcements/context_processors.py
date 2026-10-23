from .models import Announcement


def active_announcements(request):
    """
    Injects active announcements into every template context.
    Keeps DB hit to a minimum with a simple filtered query.
    """
    announcements = Announcement.objects.filter(
        is_active=True
    ).order_by('-created_at')

    return {'active_announcements': announcements}