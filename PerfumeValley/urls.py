"""
URL configuration for PerfumeValley project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.contrib.sitemaps.views import sitemap
from user_panel.sitemaps import *
import os
from django.contrib.sitemaps.views import sitemap

def robots_txt(request):
    robots_path = os.path.join(settings.BASE_DIR, 'static', 'robots.txt')
    with open(robots_path, 'r') as f:
        return HttpResponse(f.read(), content_type="text/plain")

sitemaps = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'subcategories': SubcategorySitemap,
    'products': ProductSitemap,
    'Viewall': ViewAllSitemap
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin-panel/', include('admin_panel.urls')),
    path('robots.txt', robots_txt),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),

    path('', include('user_panel.urls')),
]
if settings.DEBUG:  # Only serve media files in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
