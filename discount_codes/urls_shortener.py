from django.conf import settings
from django.urls import path, include

from . import views

urlpatterns = [
    path('<code>/', views.short_redirect, name='short_url_redirect'),
    path('<code>', views.short_redirect, name='short_url_redirect'),
    # All non-code urls will redirect as well
    path(r'^', views.short_redirect, name='short_url_base'),
    path(r'', views.short_redirect, name='short_url_base'),
    # Doesn't seem to work in debug mode but maybe will work in prod
    path(r'^.*', views.short_redirect, name='short_url_base'),

]
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
                      path('__debug__/', include(debug_toolbar.urls)),
                  ] + urlpatterns
