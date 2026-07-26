from django.contrib import admin

from .models import *

admin.site.register(Distributor)
admin.site.register(Manufacturer)
admin.site.register(PartnerDistAuth)
admin.site.register(DistributorDiscount)

class DistItemAdmin(admin.ModelAdmin):
    search_fields = ['dist_number', 'dist_name', 'dist_barcode']


admin.site.register(DistItem, DistItemAdmin)


class PurchaseOrderAdmin(admin.ModelAdmin):
    search_fields = ['po_number']


admin.site.register(PurchaseOrder, PurchaseOrderAdmin)


class POLineAdmin(admin.ModelAdmin):
    search_fields = ['po__po_number']
    autocomplete_fields = ['po']


admin.site.register(POLine, POLineAdmin)

admin.site.register(DistributorWarehouse)


class ItemWarehouseAvailabilityAdmin(admin.ModelAdmin):
    autocomplete_fields = ['dist_item']


admin.site.register(ItemWarehouseAvailability, ItemWarehouseAvailabilityAdmin)


class DistributorInventoryFileAdmin(admin.ModelAdmin):
    autocomplete_fields = ['items']


admin.site.register(DistributorInventoryFile, DistributorInventoryFileAdmin)


class DistributorInventoryLineAdmin(admin.ModelAdmin):
    autocomplete_fields = ['dist_item']


admin.site.register(DistributorInventoryLine, DistributorInventoryLineAdmin)


class PoInvoiceFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'distributor', 'po', 'status', 'update_date')
    list_filter = ('distributor', 'processed', 'processing')
    search_fields = ('filename', 'po__po_number')
    readonly_fields = ('status',)


admin.site.register(PoInvoiceFile, PoInvoiceFileAdmin)
admin.site.register(PoShipment)
admin.site.register(PoShipmentLine)
