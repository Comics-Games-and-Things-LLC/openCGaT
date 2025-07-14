from django.urls import path

from . import views

urlpatterns = [
    path('shop/manage/<slug:partner_slug>/product/<slug:product_slug>/log_dist_request/', views.log_dist_request,
         name='log_dist_request'),

]
