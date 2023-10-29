from django.urls import path

from discount_codes.views import apply_code
from .api_views import cart_set_email, cart_set_shipping_address, cart_set_pickup_partner, cart_freeze, cart_thaw, \
    mark_free_as_paid
from .views import view_cart, json_cart, remove_from_cart, update_quantity, add_to_cart

urlpatterns = [
    path('', view_cart, name='view_cart'),
    path('cart/', json_cart, name='json_cart'),
    path('remove/<int:item_id>/', remove_from_cart, name='remove_from_cart'),
    path('update/<int:item_id>/<int:quantity>/', update_quantity, name='cart_update_quantity'),
    path('add/<int:item_id>/<int:quantity>/', add_to_cart, name='add_to_cart'),

    path('api/freeze/', cart_freeze, name='cart_freeze'),
    path('api/thaw/', cart_thaw, name='cart_thaw'),

    path('api/set/email/', cart_set_email, name='cart_set_email'),
    path('api/set/shippingAddress/', cart_set_shipping_address, name='cart_set_shipping_address'),
    path('api/set/pickup_partner/', cart_set_pickup_partner, name='cart_set_pickup_partner'),
    path('api/set/mark_free_as_paid/', mark_free_as_paid, name='mark_free_as_paid'),

    path('code/<slug:code>/', apply_code, name='apply_discount_code'),
    path('code//', apply_code, name='apply_discount_code'),  # Special handling for blank code

]
