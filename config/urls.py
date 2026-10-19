"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Simple health check view
@csrf_exempt
def health_check(request):
    return JsonResponse({'status': 'healthy'})

# Root-level SEO files (sitemap_xml is reversed without a namespace in robots.txt)
from main import seo

urlpatterns = [
    path('robots.txt', seo.robots_txt),
    path('sitemap.xml', seo.sitemap_xml, name='sitemap_xml'),
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('', include('main.urls')),
    path('users/', include('users.urls')),
    path('matches/', include('matches.urls')),
    path('chats/', include('chats.urls')),
]

# Serve media files during development
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = 'main.views.error_404'
handler500 = 'main.views.error_500'
