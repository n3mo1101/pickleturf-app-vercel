from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_or_staff_required(view_func):
    """Restrict view to users with admin or staff role."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if not request.user.is_admin_or_staff:
            messages.error(request, 'Access denied.')
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return wrapper


def customer_required(view_func):
    """Restrict view to authenticated customers only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        return view_func(request, *args, **kwargs)
    return wrapper