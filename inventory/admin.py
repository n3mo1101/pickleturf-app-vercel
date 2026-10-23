from django.contrib import admin
from .models import Category, InventoryItem, Sale, SaleItem, RentalRecord


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ('name',)
    search_fields = ('name',)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'item_type', 'sale_price', 'rent_price', 'stock', 'is_active')
    list_filter   = ('item_type', 'is_active', 'category')
    search_fields = ('name',)


class SaleItemInline(admin.TabularInline):
    model  = SaleItem
    extra  = 0
    fields = ('item', 'quantity', 'unit_price', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'total', 'created_by', 'created_at')
    inlines      = [SaleItemInline]


@admin.register(RentalRecord)
class RentalRecordAdmin(admin.ModelAdmin):
    list_display  = ('item', 'renter_name', 'renter_contact', 'quantity', 'total_cost', 'status', 'rented_at')
    list_filter   = ('status',)
    search_fields = ('renter_name', 'item__name')