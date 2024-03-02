from django.contrib import admin

# Register your models here.
from checkout.models import Cart, CheckoutLine, TaxRateCache, BillingAddress, ShippingAddress
from realaddress.admin import UserAddressAdmin


class CartAdmin(admin.ModelAdmin):
    exclude = ['partner_transactions', "delivery_name", "delivery_apartment", "delivery_address", "old_billing_address"]
    search_fields = ['id', 'owner__email', 'owner__username', 'email']
    autocomplete_fields = ['owner', 'billing_address', 'shipping_address']


class CartLineAdmin(admin.ModelAdmin):
    search_fields = ['cart', 'cart__owner__email', 'cart__owner__username']
    autocomplete_fields = ['item', 'cart', 'submitted_in_cart', 'paid_in_cart', 'fulfilled_in_cart']


admin.site.register(Cart, CartAdmin)
admin.site.register(CheckoutLine, CartLineAdmin)

admin.site.register(BillingAddress, UserAddressAdmin)
admin.site.register(ShippingAddress, UserAddressAdmin)

admin.site.register(TaxRateCache)
