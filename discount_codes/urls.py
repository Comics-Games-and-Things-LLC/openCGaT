from django.urls import path

from . import views

urlpatterns = [
    path('referrers/', views.referral_index, name='referrals_index'),
    path('referrers/<referrer_slug>', views.referral_report, name='referrer_report'),

]
