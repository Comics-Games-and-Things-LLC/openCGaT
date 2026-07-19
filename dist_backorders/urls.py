from django.urls import path
from . import views

urlpatterns = [
    path('hobbytyme/', views.hobbytyme_backorder_report, name='hobbytyme_backorder_report'),
    path('hobbytyme/list/', views.hobbytyme_backorder_list, name='hobbytyme_backorder_list'),
    path('hobbytyme/<int:report_id>/', views.hobbytyme_backorder_report, name='hobbytyme_backorder_report_detail'),
]
