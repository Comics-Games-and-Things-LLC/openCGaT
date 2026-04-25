from django.conf import settings
from django.urls import path, include, re_path

from . import views

urlpatterns = [
    path('<code>/', views.short_redirect, name='short_url_redirect'),
    path('<code>', views.short_redirect, name='short_url_redirect'),
    # All non-code urls will redirect as well
    re_path(r'^', views.short_redirect, name='short_url_base'),
    re_path(r'', views.short_redirect, name='short_url_base'),
    re_path(r'^.*$', views.short_redirect, name='short_url_base'),
    re_path(r'^.*', views.short_redirect, name='short_url_base'),

]
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
                      path('__debug__/', include(debug_toolbar.urls)),
                  ] + urlpatterns
