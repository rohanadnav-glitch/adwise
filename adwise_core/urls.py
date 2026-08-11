from django.contrib import admin
from django.urls import path, include
from apps.accounts.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
    path('categories/', include('apps.categories.urls')),
    path('bookings/', include(('apps.bookings.urls', 'bookings'), namespace='bookings')),
    path('locations/', include(('apps.locations.urls', 'locations'), namespace='locations')),
    path('', home, name='home'),

]
