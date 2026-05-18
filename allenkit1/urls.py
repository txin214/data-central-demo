"""
URL configuration for allenkit1 project.

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
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.http import HttpResponse

from . import views


#celery/redis
admin.autodiscover()

# Handler for Chrome DevTools well-known path (suppresses 404)
def chrome_devtools_handler(request):
    return HttpResponse(status=404)

urlpatterns = [
    path('', views.homeview,name='home'),
    path('admin/', admin.site.urls),
    path('search/', views.search_view, name='search'),
    path('accounts/', include('accounts.urls')),
    path('crm/', include("crm.urls"),name='crm'),
    path('sitework/', include("sitework.urls"),name='sitework'),
    path('product/', include("product.urls"),name='product'),
    path('job/', include("job.urls"),name='job'),
    path('dashboard/', include("dashboard.urls"),name='dashboard'),
    path('smart_selects/', include('smart_selects.urls')),
    # Suppress Chrome DevTools well-known path 404
    path('.well-known/appspecific/com.chrome.devtools.json', chrome_devtools_handler),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
