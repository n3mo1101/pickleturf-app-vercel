from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display  = ('court', 'user', 'date', 'start_time', 'end_time', 'status', 'price')
    list_filter   = ('status', 'date', 'court')
    search_fields = ('user__email', 'court__name')
    date_hierarchy = 'date'
    ordering      = ('-date', '-start_time')