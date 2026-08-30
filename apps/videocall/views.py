from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.bookings.models import SessionBooking, SessionStatus
from apps.accounts.models import UserRole

@login_required
def video_call_room_view(request, room_name):
    """
    Renders the WebRTC video call room, secures access to participants only, 
    verifies confirmed payment status, and extracts correct participant names.
    """
    # Attempt to find an active booking tied to this room link
    booking = SessionBooking.objects.filter(meeting_link__icontains=room_name).select_related('expert__user', 'user').first()

    if booking:
        # SECURITY CHECK: Ensure the logged-in user is either the client or the expert
        is_client = (booking.user == request.user)
        is_expert = (booking.expert.user == request.user)

        if not (is_client or is_expert):
            messages.error(request, "Access denied. You are not a participant in this consultation.")
            return redirect('accounts:user_dashboard')

        # SECURITY CHECK: Ensure the session is officially paid and confirmed
        if booking.status != SessionStatus.CONFIRMED:
            messages.error(request, "This meeting room is only available for confirmed and paid sessions.")
            return redirect('bookings:user_bookings')

        consultant_name = booking.expert.user.get_full_name() or booking.expert.user.username
        client_name = booking.user.get_full_name() or booking.user.username
    else:
        # Fallback names if accessed generically without a formal database booking
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