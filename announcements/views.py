from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_or_staff_required
from .forms import AnnouncementForm
from .models import Announcement


@admin_or_staff_required
def admin_list_view(request):
    announcements = Announcement.objects.all()
    return render(request, 'announcements/admin_list.html', {
        'announcements': announcements,
    })


@admin_or_staff_required
def admin_create_view(request):
    form = AnnouncementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        messages.success(request, 'Announcement created.')
        return redirect('announcements:admin_list')
    return render(request, 'announcements/form.html', {
        'form':  form,
        'title': 'Create Announcement',
    })


@admin_or_staff_required
def admin_edit_view(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    form = AnnouncementForm(request.POST or None, instance=announcement)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Announcement updated.')
        return redirect('announcements:admin_list')
    return render(request, 'announcements/form.html', {
        'form':         form,
        'title':        f'Edit — {announcement.title}',
        'announcement': announcement,
    })


@admin_or_staff_required
def admin_takedown_view(request, pk):
    """Toggle is_active off — takes down the announcement."""
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        announcement.is_active = False
        announcement.save(update_fields=['is_active'])
        messages.success(
            request, f'"{announcement.title}" has been taken down.'
        )
    return redirect('announcements:admin_list')


@admin_or_staff_required
def admin_delete_view(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f'"{title}" deleted.')
    return redirect('announcements:admin_list')