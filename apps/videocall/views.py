from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.bookings.models import SessionBooking
from apps.accounts.models import UserRole

@login_required
def video_call_room_view(request, room_name):
    """
    Renders the WebRTC video call room and extracts the correct consultant and client names.
    """
    # Attempt to find an active booking tied to this room link if applicable
    booking = SessionBooking.objects.filter(meeting_link__icontains=room_name).select_related('expert__user', 'user').first()

    if booking:
        consultant_name = booking.expert.user.get_full_name() or booking.expert.user.username
        client_name = booking.user.get_full_name() or booking.user.username
    else:
        # Fallback names if accessed generically
        if request.user.role == UserRole.EXPERT:
            consultant_name = request.user.get_full_name() or request.user.username
            client_name = "Client"
        else:
            consultant_name = "Expert Consultant"
            client_name = request.user.get_full_name() or request.user.username

    context = {
        'room_name': room_name,
        'consultant_name': consultant_name,
        'client_name': client_name,
    }
    return render(request, 'videocall/room.html', context)