from django.urls import path
from . import views

urlpatterns = [
    path('', views.box_inventory, name='box_inventory'),
    path('<int:box_id>/adjust/', views.adjust_box_inventory, name='adjust_box_inventory'),
]
