from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum
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
        status__in=[Booking.Status.RESERVED, Booking.Status.COMPLETED],
    )
    summary = Booking.objects.filter(user=request.user).aggregate(
        total_bookings=Count('id'),
    )

    from transactions.models import Transaction
    total_spent = (
        Transaction.objects
        .filter(
            user=request.user,
            payment_status=Transaction.PaymentStatus.PAID,
        )
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    stats = {
        'total_bookings': summary['total_bookings'] or 0,
        'total_spent':    total_spent,
        'courts_played':  played.values('court_id').distinct().count(),
    }

    return render(request, 'accounts/profile.html', {
        'form':  form,
        'stats': stats,
    })
