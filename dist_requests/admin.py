from django.contrib import admin

from dist_requests.models import DistRequest, DistRequestLine


# Register your models here.
@admin.register(DistRequest)
class DistRequestAdmin(admin.ModelAdmin):
    list_display = ('request_name', 'distributor', 'date', 'partner', )
    list_filter = ('partner', 'distributor', 'date')
    search_fields = ('request_name',)
    ordering = ('date', 'distributor', 'request_name')


@admin.register(DistRequestLine)
class DistRequestLineAdmin(admin.ModelAdmin):
    list_display = ('product', 'request')
    list_filter = ('product__name', 'request__distributor')
    search_fields = ('product__name',)
    ordering = ('request__date', 'request__distributor', 'product__name', 'request__request_name')
    autocomplete_fields = ['request', 'product']
