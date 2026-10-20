from django.urls import path
from . import views, seo

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('stats/', views.stats, name='stats'),
    path('manifest.webmanifest', seo.manifest, name='manifest'),
] 