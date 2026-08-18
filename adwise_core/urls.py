from django.contrib import admin
from django.urls import path, include
from apps.accounts.views import home
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
    path('categories/', include('apps.categories.urls')),
    path('bookings/', include(('apps.bookings.urls', 'bookings'), namespace='bookings')),
    path('locations/', include(('apps.locations.urls', 'locations'), namespace='locations')),
    path('call/', include('apps.videocall.urls')),
    path('', home, name='home'),

]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
