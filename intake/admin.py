from django.contrib import admin

from .models import *

# Register your models here.

admin.site.register(Distributor)
admin.site.register(DistributorDiscount)

admin.site.register(DistItem)

admin.site.register(PurchaseOrder)
admin.site.register(POLine)

admin.site.register(DistributorWarehouse)
admin.site.register(DistributorInventoryFile)
