from django.contrib import admin

from .models import *


# Register your models here.


class ProductAdmin(admin.ModelAdmin):
    search_fields = ['name', 'barcode']
    autocomplete_fields = []


class ItemAdmin(admin.ModelAdmin):
    search_fields = ['product__name', 'product__barcode']
    autocomplete_fields = ['product']


admin.site.register(Product, ProductAdmin)
admin.site.register(Publisher)
admin.site.register(Category)
admin.site.register(Partner)
admin.site.register(CardCondition)

admin.site.register(Item, ItemAdmin)
admin.site.register(InventoryItem, ItemAdmin)
admin.site.register(MadeToOrder, ItemAdmin)
# admin.site.register(ComicItem, ItemAdmin)
# admin.site.register(CardItem, ItemAdmin)
admin.site.register(UsedItem, ItemAdmin)

admin.site.register(ProductImage)
