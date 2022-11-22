from django.urls import path
from .views import *

urlpatterns = [
    path('', partner_orders, name='partner_orders'),

    path('<int:cart_id>/', partner_order_details, name='partner_order_details'),
    path('<int:cart_id>/printout/', partner_order_printout, name='partner_order_printout'),
    path('<int:cart_id>/ready_for_pickup/', partner_order_ready_for_pickup, name='partner_order_ready_for_pickup'),

    path('<int:cart_id>/completed/', partner_order_mark_completed, name='partner_order_mark_completed'),
    path('<int:cart_id>/paid/', partner_order_mark_paid, name='partner_order_mark_paid'),
    path('<int:cart_id>/cancelled/', past_order_mark_cancelled, name='partner_order_mark_cancelled'),

    path('pos/', pos, name='pos'),
    path('pos/data/', partner_cart_endpoint, name='partner_cart_endpoint'),
    path('pos/<int:cart_id>/data/', partner_cart_endpoint, name='partner_cart_endpoint'),

    path('pos/new/', pos_create_cart, name='pos_new_cart'),

    path('pos/<int:cart_id>/', pos, name='pos'),

    path('pos/<int:cart_id>/update/<int:item_id>/', partner_update_line,
         name='partner_update_line'),
    path('pos/<int:cart_id>/remove/<int:item_id>/', partner_remove_line,
         name='pos_remove_line'),
    path('pos/<int:cart_id>/add/<barcode>/', pos_add_item, name='pos_add_item'),
    path('pos/<int:cart_id>/add_custom/', pos_add_custom, name='pos_add_custom'),
    path('pos/<int:cart_id>/set_owner/', pos_set_owner, name='pos_set_owner'),

    path('pos/<int:cart_id>/cash/', pos_pay_cash, name='pos_pay_cash'),
    path('pos/<int:cart_id>/stripe/', pos_create_stripe_payment, name='pos_create_stripe_payment'),

    path('pos/stripe_terminal_connection_token/', stripe_terminal_connection_token,
         name='stripe_terminal_connection_token'),

    path('pos/<int:cart_id>/capture/', stripe_capture, name='stripe_capture'),

]
