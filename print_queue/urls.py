from django.urls import path
from . import views

urlpatterns = [
    path('', views.PrintQueueListView.as_view(), name='print_queue_list'),
    path('mark_printed/<int:item_id>/', views.mark_printed, name='mark_printed'),
    path('mark_restickered/<int:item_id>/', views.mark_restickered, name='mark_restickered'),
    path('mark_all_restickered/', views.mark_all_restickered, name='mark_all_restickered'),
    path('mark_all_finished/', views.mark_all_finished, name='mark_all_finished'),

    # New Print Queue API
    path('printers/register/', views.register_printer, name='printer_register'),
    path('printers/online/', views.get_online_printers, name='printers_online'),
    path('jobs/add/', views.add_print_job, name='print_job_add'),
    path('jobs/claim/', views.claim_print_job, name='print_job_claim'),
    path('jobs/<int:job_id>/mark_printed/', views.mark_job_printed, name='print_job_mark_printed'),
    path('stream/', views.print_job_stream, name='print_job_stream'),
]
