from django.urls import path, include

from . import views

urlpatterns = [
    path('', views.product_list, name='shop'),
    path('manage/<slug:partner_slug>/', views.product_list, name='manage_products'),
    path('manage/<slug:partner_slug>/create/', views.add_edit_product, name='create_new_product'),

    path('product/<product_slug>/', views.product_details, name='product_detail'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/', views.manage_product, name='manage_product'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/edit/', views.add_edit_product, name='edit_product'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/edit_related/', views.edit_related_products,
         name='edit_related_products'),

    path('manage/<slug:partner_slug>/product/<slug:product_slug>/copy/', views.copy_product, name='copy_product'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/replace/', views.replace_product, name='replace_product'),

    path('manage/<slug:partner_slug>/product/<slug:product_slug>/main_image/', views.upload_primary_image,
         name='upload_primary_image'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/additional_image/', views.upload_additional_image,
         name='upload_additional_image'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/images/', views.manage_image_upload_endpoint,
         name='manage_image_upload_endpoint'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/remove_image/<image_id>', views.remove_image,
         name='remove_image'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/set_primary_image/<image_id>',
         views.set_image_as_primary,
         name='set_image_as_primary'),

    path('manage/<slug:partner_slug>/product/<slug:product_slug>/delete/<int:confirm>/', views.delete_product,
         name='delete_product'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/why_visible/', views.why_visibile, name='why_visible'),

    path('manage/<slug:partner_slug>/product/<slug:product_slug>/', include('digitalitems.urls-management')),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/item/mto/add/', views.add_mto, name='add_mto_item'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/item/inventory/add/', views.add_inventory_item,
         name='add_inventory_item'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/item/<item_id>/edit/', views.edit_item,
         name='edit_item'),
    path('manage/<slug:partner_slug>/product/<slug:product_slug>/item/<item_id>/delete/<int:confirm>/',
         views.delete_item,
         name='delete_item'),

    path('manage/<slug:partner_slug>/custom_charge/create/', views.create_custom_charge,
         name='create_custom_charge'),

    path('manage/<slug:partner_slug>/bulk/', views.bulk_edit, name='bulk_edit'),


    path('item/<item_id>/', views.get_item_details, name='get_item_details'),
]
