from django.urls import path

from . import views

urlpatterns = [
    path('intake/', views.index, name='intake_home'),
    path('intake/<barcode>', views.intake_item_view, name='intake_item'),
    path('intake/add/<barcode>', views.intake_item_view, name='intake_add'),
    path('intake/create/<barcode>', views.create_endpoint, name='intake_create'),
    path('intake/get_image/<item_id>/', views.get_image, name='get_image'),
    path('intake/get_order_image/<checkoutline_id>/', views.get_order_image, name='get_order_image'),

    path('distributors/', views.distributors, name='distributors'),

    path('pricing_rules/', views.pricing_rules_list, name='pricing_rules'),
    path('pricing_rules/add_rule/', views.edit_rule, name='add_rule'),
    path('pricing_rules/edit_rule/<rule_id>/', views.edit_rule, name='edit_rule'),

    path('purchase_orders/', views.po_list, name='purchase_orders'),
    path('purchase_orders/create/', views.edit_po, name='create_po'),
    path('purchase_orders/edit/<po_id>/', views.edit_po, name='edit_po'),
    path('purchase_orders/delete/<po_id>/<confirm>/', views.delete_po, name='delete_po'),
    path('purchase_orders/<po_id>/', views.po_details, name='po_details'),
    path('purchase_orders/<po_id>/add/', views.edit_po_line, name='add_po_line'),
    path('purchase_orders/<po_id>/scan/<barcode>/', views.scan_item_to_po, name='add_po_line'),
    path('purchase_orders/<po_id>/edit/<po_line_id>/', views.edit_po_line, name='edit_po_line'),
    path('purchase_orders/<po_id>/delete/<po_line_id>/<confirm>/', views.delete_po_line, name='delete_po_line'),

]
