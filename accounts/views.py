from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import render, redirect
from bookings.models import Booking
from .forms import ProfileUpdateForm


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    played = Booking.objects.filter(
        user=request.user,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
    )
    summary = Booking.objects.filter(user=request.user).aggregate(
        total_bookings=Count('id'),
        total_spent=Sum(
            'price',
            filter=Q(
                status__in=[
                    Booking.Status.CONFIRMED,
                    Booking.Status.COMPLETED,
                ]
            ),
        ),
    )

    stats = {
        'total_bookings': summary['total_bookings'] or 0,
        'total_spent':    summary['total_spent'] or 0,
        'courts_played':  played.values('court_id').distinct().count(),
    }

    return render(request, 'accounts/profile.html', {
        'form':  form,
        'stats': stats,
    })
