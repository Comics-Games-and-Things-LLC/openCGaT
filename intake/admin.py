from django.contrib import admin

from .models import *

admin.site.register(Distributor)
admin.site.register(DistributorDiscount)

admin.site.register(DistItem)


class PurchaseOrderAdmin(admin.ModelAdmin):
    search_fields = ['po_number']


admin.site.register(PurchaseOrder, PurchaseOrderAdmin)


class POLineAdmin(admin.ModelAdmin):
    search_fields = ['po__po_number']
    autocomplete_fields = ['po']


admin.site.register(POLine, POLineAdmin)

admin.site.register(DistributorWarehouse)
admin.site.register(DistributorInventoryFile)


class PoInvoiceFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'distributor', 'po', 'status', 'update_date')
    list_filter = ('distributor', 'processed', 'processing')
    search_fields = ('filename', 'po__po_number')
    readonly_fields = ('status',)


admin.site.register(PoInvoiceFile, PoInvoiceFileAdmin)
