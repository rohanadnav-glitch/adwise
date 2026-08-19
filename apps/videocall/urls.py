from django.urls import path
from . import views

app_name = 'videocall'

urlpatterns = [
    path('<str:room_name>/', views.video_call_room_view, name='room'), # Updated name
]