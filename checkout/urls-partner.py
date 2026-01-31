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
    path('<int:cart_id>/update/', partner_order_status_update, name='partner_order_status_update'),

    path('<int:cart_id>/comments/', update_partner_comments, name='partner_update_comments'),

    path('<int:cart_id>/line/<int:line_id>/cancel/', partner_cancel_line,
         name='partner_cancel_line'),
    path('<int:cart_id>/line/<int:line_id>/ready/', partner_ready_line,
         name='partner_ready_line'),
    path('<int:cart_id>/line/<int:line_id>/complete/', partner_complete_line,
         name='partner_complete_line'),
    path('<int:cart_id>/line/<int:line_id>/split/', partner_split_line,
         name='partner_split_line'),

    path('pos/', pos, name='pos'),
    path('pos/data/', partner_cart_endpoint, name='partner_cart_endpoint'),
    path('pos/cart_list/', pos_cart_list_endpoint, name='pos_cart_list_endpoint'),
    path('pos/<int:cart_id>/data/', partner_cart_endpoint, name='partner_cart_endpoint'),
    path('pos/<int:cart_id>/cart/', pos_active_cart_endpoint, name='partner_cart_only_endpoint'),
    path('pos/<int:cart_id>/complete/', pos_mark_complete, name='pos_mark_complete'),

    path('pos/new/', pos_create_cart, name='pos_new_cart'),

    path('pos/<int:cart_id>/', pos, name='pos'),

    path('pos/<int:cart_id>/update/<int:item_id>/', partner_update_line,
         name='partner_update_line'),
    path('pos/<int:cart_id>/remove/<int:item_id>/', partner_remove_line,
         name='pos_remove_line'),
    path('pos/<int:cart_id>/add/<barcode>/', pos_add_item, name='pos_add_item'),
    path('pos/<int:cart_id>/add_custom/', pos_add_custom, name='pos_add_custom'),
    path('pos/<int:cart_id>/set_owner/', pos_set_owner, name='pos_set_owner'),
    path('pos/<int:cart_id>/suggest_owner/', pos_suggest_owner, name='pos_suggest_owner'),
    path('pos/<int:cart_id>/clear_owner/', pos_clear_owner, name='pos_clear_owner'),

    path('pos/<int:cart_id>/set_code/', pos_set_code, name='pos_set_code'),

    path('pos/<int:cart_id>/cash/', pos_pay_cash, name='pos_pay_cash'),
    path('pos/<int:cart_id>/stripe/', pos_create_stripe_payment, name='pos_create_stripe_payment'),

    path('pos/stripe_terminal_connection_token/', stripe_terminal_connection_token,
         name='stripe_terminal_connection_token'),

    path('pos/<int:cart_id>/capture/', stripe_capture, name='stripe_capture'),

    path('pre_and_back_orders/', all_pre_and_back_orders, name='partner_pre_and_back_orders'),
    path('tasks/', tasks, name='partner_tasks'),

]
