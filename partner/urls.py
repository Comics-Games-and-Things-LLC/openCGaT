from django.urls import path, include

from . import views

urlpatterns = [

    path('', views.partner_list, name='partners'),
    path('select/', views.partner_select, name='admin_partner_list'),

    path('<partner_slug>/', views.partner_info, name='partner_info'),

    path('admin/billing/', views.admin_billing, name='admin_billing'),
    path('admin/update_balance/', views.admin_update_billing, name='admin_update_balance'),
    path('admin/reset_balance/', views.admin_reset_billing, name='admin_reset_balance'),
    path('admin/billing/summary_breakout/<summary_id>', views.admin_summary_breakout, name='admin_summary_breakout'),
    path('admin/customers/', views.admin_customer_list, name='admin_customer_list'),
    path('admin/customers/<user_id>/', views.admin_customer_details, name='admin_customer_details'),

    path('<partner_slug>/home/', views.partner_homepage, name='partner_homepage'),
    path('<partner_slug>/financials/', views.financial, name='partner_financial'),
    path('<partner_slug>/statements/', include('billing.urls')),

    path('<partner_slug>/billing/', views.partner_billing, name='partner_billing'),
    path('<partner_slug>/billing/csv/', views.export_pt_csv, name='billing_csv_export'),
    path('<partner_slug>/billing/sales_csv/', views.export_pt_sales_csv, name='billing_csv_export_sales_only'),

    path('<partner_slug>/billing/summary_breakout/<summary_id>', views.summary_breakout, name='summary_breakout'),
    path('<partner_slug>/orders/', include('checkout.urls-partner')),
    path('<partner_slug>/financial/', include('financial.urls')),

    path('<partner_slug>/update_balance/', views.update_billing, name='partner_update_balance'),
    path('<partner_slug>/reset_balance/', views.reset_billing, name='partner_reset_balance'),
    path('<partner_slug>/customers/', views.customer_list, name='partner_customer_list'),
    path('<partner_slug>/customers/<user_id>/', views.customer_details, name='partner_customer_details'),

    path('<partner_slug>/discount_all/', views.discount_all, name='partner_discount_all'),
    path('<partner_slug>/', include('discount_codes.urls')),

]
