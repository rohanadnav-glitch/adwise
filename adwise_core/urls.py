from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('categories/', include('apps.categories.urls')),
    # main urls.py
    path('bookings/', include(('apps.bookings.urls', 'bookings'), namespace='bookings')),
    path('locations/', include('apps.locations.urls', namespace='locations')),
    path('', lambda request: redirect('login')),
    # adwise_core/urls.py
    path('locations/', include(('apps.locations.urls', 'locations'), namespace='locations')),
]
