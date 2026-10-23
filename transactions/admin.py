from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ('tx_type', 'user', 'amount', 'payment_status', 'created_at')
    list_filter   = ('tx_type', 'payment_status')
    search_fields = ('user__email', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')