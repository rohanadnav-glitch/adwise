# Create your views here.
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def room_view(request, room_name):
    return render(request, 'videocall/room.html', {'room_name': room_name})