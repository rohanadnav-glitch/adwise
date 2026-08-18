from django.urls import path
from . import views

app_name = 'videocall'

urlpatterns = [
    path('<str:room_name>/', views.room_view, name='room'),
]