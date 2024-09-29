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
