from django.contrib import admin

from box_counter.models import BoxPurchase, BoxInventory, BoxUse

# Register your models here.
admin.site.register(BoxPurchase)
admin.site.register(BoxInventory)
admin.site.register(BoxUse)
