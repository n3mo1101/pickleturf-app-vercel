from django.contrib import admin

from .models import Booking, BookingSlot


class BookingSlotInline(admin.TabularInline):
    model = BookingSlot
    extra = 0
    can_delete = False
    fields = ('start_time', 'end_time', 'price', 'is_active')
    readonly_fields = ('end_time', 'is_active')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display  = (
        'court', 'user', 'date', 'start_time', 'end_time',
        'status', 'price',
    )
    list_filter   = ('status', 'date', 'court')
    search_fields = ('user__email', 'court__name')
    date_hierarchy = 'date'
    ordering      = ('-date', '-start_time')
    inlines       = [BookingSlotInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        booking = form.instance
        booking.sync_summary_from_slots()
        # A changed reservation total invalidates any in-flight checkout.
        try:
            tx = booking.transaction
        except Exception:
            tx = None
        if tx:
            tx.amount = booking.price
            tx.provider_checkout_id = ''
            tx.save(
                update_fields=[
                    'amount', 'provider_checkout_id', 'updated_at',
                ]
            )
