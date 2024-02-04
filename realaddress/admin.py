from django.contrib import admin

from realaddress.models import UserAddress, RealCountry


class UserAddressAdmin(admin.ModelAdmin):
    search_fields = ['search_text']


class CountryAdmin(admin.ModelAdmin):
    list_display = [
        '__str__',
        'display_order'
    ]
    list_filter = [
        'is_shipping_country'
    ]
    search_fields = [
        'name',
        'printable_name',
        'iso_3166_1_a2',
        'iso_3166_1_a3'
    ]


admin.site.register(UserAddress, UserAddressAdmin)
admin.site.register(RealCountry, CountryAdmin)
