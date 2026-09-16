from django.urls import path
from . import views

urlpatterns = [
    path('', views.PrintQueueListView.as_view(), name='print_queue_list'),
    path('mark_printed/<int:item_id>/', views.mark_printed, name='mark_printed'),
    path('mark_restickered/<int:item_id>/', views.mark_restickered, name='mark_restickered'),
]
