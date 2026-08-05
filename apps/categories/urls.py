from django.urls import path
from . import views

urlpatterns = [
    path('get-subcategories/', views.get_subcategories_api, name='get_subcategories'),
]