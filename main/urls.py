from django.urls import path
from . import views, seo

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('manifest.webmanifest', seo.manifest, name='manifest'),
] 