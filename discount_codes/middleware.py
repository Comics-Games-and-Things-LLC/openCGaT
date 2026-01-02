# main_project/middleware.py

from discount_codes.models import URLShortener

IS_SHORT_CACHE = {}


class ShorteningMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        site = request.site

        # If this is a short url site, use the alternate url config
        if _get_is_shortener_from_cache(site.id):
            request.urlconf = 'discount_codes.urls_shortener'

        return self.get_response(request)


def _get_is_shortener_from_cache(site_id):
    if site_id not in IS_SHORT_CACHE:
        IS_SHORT_CACHE[site_id] = URLShortener.objects.filter(short_site__id=site_id).exists()
    return IS_SHORT_CACHE[site_id]
