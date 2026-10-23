from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'bookings'

urlpatterns = [
    # Customer
    path('',                    views.availability_view,      name='availability'),
    path('my/',                 views.my_bookings_view,        name='my_bookings'),
    path('new/',                views.booking_create_view,     name='create'),
    path('<int:pk>/cancel/',    views.booking_cancel_view,     name='cancel'),

    # Admin/Staff
    path('admin/',              views.admin_booking_list_view,   name='admin_list'),
    path('admin/new/',          RedirectView.as_view(pattern_name='bookings:create', permanent=False), name='admin_create'),
    path('admin/<int:pk>/cancel/', views.admin_booking_cancel_view, name='admin_cancel'),
    path('admin/<int:pk>/status/', views.admin_booking_status_view, name='admin_status'),
    path('staff/', views.staff_bookings_view, name='staff_bookings'),
]