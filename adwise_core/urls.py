from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
    path('categories/', include('apps.categories.urls')),
    path('bookings/', include(('apps.bookings.urls', 'bookings'), namespace='bookings')),
    path('locations/', include(('apps.locations.urls', 'locations'), namespace='locations')),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),

]
