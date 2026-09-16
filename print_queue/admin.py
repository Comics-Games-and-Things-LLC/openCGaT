from django.contrib import admin
from .models import PrintQueueItem


@admin.register(PrintQueueItem)
class PrintQueueItemAdmin(admin.ModelAdmin):
    list_display = ('inventory_item', 'old_price', 'new_price', 'quantity_at_adjustment', 'printed', 'restickered', 'created_at')
    list_filter = ('printed', 'restickered')
    search_fields = ('inventory_item__product__name', 'inventory_item__product__barcode')
