from django.urls import path
from . import views

urlpatterns = [

    path('get-districts/', views.get_districts, name='get_districts'),
    path('get-cities/', views.get_cities, name='get_cities'),
]