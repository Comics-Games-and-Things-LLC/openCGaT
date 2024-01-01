from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='inv_report_home'),
    path('<report_id>/', views.report_details, name='report'),
    path('<report_id>/add/<barcode>/', views.add, name='report_add'),
    path('<report_id>/<location_id>/', views.report_details, name='report'),
    path('<report_id>/<location_id>/add/<barcode>/', views.add, name='report_add'),
    path('<report_id>/delete/<report_line_id>/<confirm>', views.delete_inv_report_line, name='delete_inv_report_line'),
    path('<report_id>/<location_id>/delete/<report_line_id>/<confirm>', views.delete_inv_report_line,
         name='delete_inv_report_line'),

]
