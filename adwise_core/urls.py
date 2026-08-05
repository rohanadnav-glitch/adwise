from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('locations/', include('apps.locations.urls')),
    path('categories/', include('apps.categories.urls')),
    path('bookings/', include('apps.bookings.urls')),
    path('', lambda request: redirect('login')),
]