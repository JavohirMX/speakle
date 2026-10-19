"""SEO helpers: canonical URLs, noindex header, robots.txt, sitemap.xml, web manifest."""
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.urls import reverse

# Only these paths are meant to appear in search. Everything else (login, app, chat,
# admin, password reset) is sent with "X-Robots-Tag: noindex".
PUBLIC_PATHS = ('/', '/users/register/')
TECHNICAL_PATHS = ('/robots.txt', '/sitemap.xml', '/manifest.webmanifest')


def site_origin(request):
    configured = getattr(settings, 'SITE_URL', '')
    return configured.rstrip('/') if configured else f'{request.scheme}://{request.get_host()}'


def seo_context(request):
    origin = site_origin(request)
    return {'site_origin': origin, 'canonical_url': origin + request.path}


class NoIndexMiddleware:
    """Adds X-Robots-Tag: noindex to every non-public page, including error pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path in TECHNICAL_PATHS or request.path.startswith(('/static/', '/media/')):
            return response
        if request.path not in PUBLIC_PATHS or response.status_code >= 400:
            response['X-Robots-Tag'] = 'noindex'
        return response


def robots_txt(request):
    # Private pages are NOT disallowed on purpose: Google can only see a noindex
    # directive on pages it is allowed to crawl.
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        '',
        f'Sitemap: {site_origin(request)}{reverse("sitemap_xml")}',
        '',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def sitemap_xml(request):
    origin = site_origin(request)
    urls = ''.join(f'<url><loc>{origin}{p}</loc></url>' for p in PUBLIC_PATHS)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>')
    return HttpResponse(xml, content_type='application/xml')


def manifest(request):
    data = {
        'name': 'Speakle',
        'short_name': 'Speakle',
        'description': 'Free two-way language exchange by video and text chat.',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#fff9ec',
        'theme_color': '#ffc61a',
        'icons': [
            {'src': static('img/icon-192.png'), 'sizes': '192x192', 'type': 'image/png'},
            {'src': static('img/icon-512.png'), 'sizes': '512x512', 'type': 'image/png'},
            {'src': static('img/icon-maskable-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }
    return JsonResponse(data, content_type='application/manifest+json')
