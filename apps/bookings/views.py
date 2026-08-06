from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import date
from apps.accounts.models import ExpertProfile, UserRole
from .models import ExpertAvailability, SessionBooking, SessionStatus, Notification
from .forms import AvailabilitySlotForm
from .utils import send_session_email_notification
from .models import Review
from .forms import ReviewForm
from django.http import JsonResponse




# ==========================================
# 1. HELPER: CREATE NOTIFICATION
# ==========================================
def create_notification(user, title, message):
    Notification.objects.create(
        user=user,
        title=title,
        message=message
    )


# ==========================================
# 2. EXPERT SCHEDULE MANAGEMENT
# ==========================================
@login_required
def schedule_manager_view(request):
    """ Allows experts to view, add, and manage their consultation availability slots """
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access restricted to Expert accounts.")
        return redirect('user_dashboard')

    # 1. Fetch expert profile
    expert_profile = get_object_or_404(ExpertProfile, user=request.user)

    # 2. Handle slot creation form submission
    if request.method == 'POST':
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')

        if date and start_time and end_time:
            # Check for existing duplicate slot
            existing_slot = ExpertAvailability.objects.filter(
                expert=expert_profile,
                date=date,
                start_time=start_time,
                end_time=end_time
            ).exists()

            if existing_slot:
                messages.warning(request, "You have already created a slot for this exact date and time range.")
            else:
                ExpertAvailability.objects.create(
                    expert=expert_profile,
                    date=date,
                    start_time=start_time,
                    end_time=end_time,
                    is_booked=False
                )
                messages.success(request, "New availability slot added successfully!")
                return redirect('schedule_manager')
        else:
            messages.error(request, "Please fill in all date and time fields.")

    # 3. Retrieve all slots for this expert, ordered by date and start time
    slots = ExpertAvailability.objects.filter(expert=expert_profile).order_by('date', 'start_time')

    # 4. Pass expert_profile and slots to context
    context = {
        'expert_profile': expert_profile,
        'slots': slots,
    }
    return render(request, 'bookings/schedule_manager.html', context)

@login_required
def delete_slot_view(request, slot_id):
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access denied.")
        return redirect('user_dashboard')

    slot = get_object_or_404(ExpertAvailability, id=slot_id, expert__user=request.user)

    if slot.is_booked:
        messages.error(request, "Cannot delete a slot that has already been booked.")
    else:
        slot.delete()
        messages.success(request, "Availability slot removed successfully.")

    return redirect('schedule_manager')


# ==========================================
# 3. DYNAMIC SEARCH & FILTER ENGINE
# ==========================================
@login_required
def search_experts_view(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    state_id = request.GET.get('state')
    district_id = request.GET.get('district')
    city_id = request.GET.get('city')
    max_fee = request.GET.get('max_fee')
    selected_date = request.GET.get('date')

    experts = ExpertProfile.objects.select_related(
        'user', 'category', 'subcategory', 'state', 'district', 'city'
    ).all()

    if query:
        experts = experts.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(qualification__icontains=query) |
            Q(bio__icontains=query)
        )

    if category_id and category_id.isdigit():
        experts = experts.filter(category_id=category_id)
    if subcategory_id and subcategory_id.isdigit():
        experts = experts.filter(subcategory_id=subcategory_id)

    if state_id and state_id.isdigit():
        experts = experts.filter(state_id=state_id)
    if district_id and district_id.isdigit():
        experts = experts.filter(district_id=district_id)
    if city_id and city_id.isdigit():
        experts = experts.filter(city_id=city_id)

    if max_fee:
        try:
            experts = experts.filter(hourly_rate__lte=float(max_fee))
        except ValueError:
            pass

    if selected_date:
        experts = experts.filter(
            availabilities__date=selected_date,
            availabilities__is_booked=False
        ).distinct()

    from apps.categories.models import Category
    from apps.locations.models import State

    context = {
        'experts': experts,
        'categories': Category.objects.all(),
        'states': State.objects.all(),
        'selected_q': query,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else '',
        'selected_subcategory': int(subcategory_id) if subcategory_id and subcategory_id.isdigit() else '',
        'selected_state': int(state_id) if state_id and state_id.isdigit() else '',
        'selected_district': int(district_id) if district_id and district_id.isdigit() else '',
        'selected_city': int(city_id) if city_id and city_id.isdigit() else '',
        'selected_max_fee': max_fee,
        'selected_date': selected_date,
    }
    return render(request, 'bookings/search_results.html', context)


@login_required
def expert_detail_view(request, expert_id):
    expert = get_object_or_404(
        ExpertProfile.objects.select_related('user', 'category', 'subcategory', 'state', 'district', 'city'),
        id=expert_id
    )

    available_slots = ExpertAvailability.objects.filter(
        expert=expert,
        date__gte=date.today(),
        is_booked=False
    ).order_by('date', 'start_time')

    return render(request, 'bookings/expert_detail.html', {
        'expert': expert,
        'available_slots': available_slots
    })


# ==========================================
# 4. USER: REQUEST SESSION & BOOKINGS
# ==========================================
@login_required
@transaction.atomic
def request_session_view(request, slot_id):
    if request.user.role != UserRole.USER:
        messages.error(request, "Only registered users can request expert sessions.")
        return redirect('search_experts')

    slot = get_object_or_404(
        ExpertAvailability.objects.select_for_update(), 
        id=slot_id, 
        is_booked=False
    )

    existing_request = SessionBooking.objects.filter(
        user=request.user, 
        slot=slot, 
        status__in=[SessionStatus.REQUESTED, SessionStatus.ACCEPTED, SessionStatus.CONFIRMED]
    ).exists()

    if existing_request:
        messages.warning(request, "You already have an active request or booking for this slot.")
        return redirect('expert_detail', expert_id=slot.expert.id)

    SessionBooking.objects.create(
        user=request.user,
        expert=slot.expert,
        slot=slot,
        status=SessionStatus.REQUESTED
    )

    create_notification(
        user=slot.expert.user,
        title="New Session Request Received",
        message=f"{request.user.get_full_name()} requested a consultation for {slot.date.strftime('%b %d, %Y')} at {slot.start_time.strftime('%I:%M %p')}."
    )

    messages.success(request, "Session request sent to the expert!")
    return redirect('user_bookings')


@login_required
def expert_requests_view(request):
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access restricted to Expert accounts.")
        return redirect('user_dashboard')

    expert = get_object_or_404(ExpertProfile, user=request.user)
    requests_list = SessionBooking.objects.filter(expert=expert).select_related('user', 'slot')

    # ❌ WRONG TEMPLATE: It is pointing to user_bookings.html
    return render(request, 'bookings/expert_requests.html', {
        'requests_list': requests_list
    })

@login_required
@transaction.atomic
def expert_action_view(request, booking_id, action):
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access denied.")
        return redirect('user_dashboard')

    booking = get_object_or_404(
        SessionBooking.objects.select_for_update(), 
        id=booking_id, 
        expert__user=request.user
    )

    if action == 'accept':
        booking.status = SessionStatus.ACCEPTED
        booking.set_payment_deadline()
        booking.save()

        # In-App Notification
        create_notification(
            user=booking.user,
            title="Session Request Accepted!",
            message=f"{booking.expert.user.get_full_name()} accepted your request. Complete payment within 24 hours."
        )

        # Trigger Email Alert to User
        send_session_email_notification(
            recipient_email=booking.user.email,
            subject="Action Required: Your Adwise Session Request is Accepted!",
            template_name='emails/booking_status_email.html',
            context={
                'user_name': booking.user.first_name,
                'message_body': f"Great news! {booking.expert.user.get_full_name()} has accepted your consultation request. Please log in and complete your payment within 24 hours to secure your slot.",
                'expert_name': booking.expert.user.get_full_name(),
                'session_date': booking.slot.date.strftime('%B %d, %Y'),
                'session_time': f"{booking.slot.start_time.strftime('%I:%M %p')} - {booking.slot.end_time.strftime('%I:%M %p')}",
                'action_url': 'http://127.0.0.1:8000/bookings/my-bookings/'
            }
        )
        messages.success(request, "Request accepted and notification email sent to user.")

    elif action == 'reject':
        booking.status = SessionStatus.REJECTED
        booking.save()

        create_notification(
            user=booking.user,
            title="Session Request Update",
            message=f"{booking.expert.user.get_full_name()} was unable to accept your request."
        )

        # Trigger Rejection Email
        send_session_email_notification(
            recipient_email=booking.user.email,
            subject="Update on your Adwise Session Request",
            template_name='emails/booking_status_email.html',
            context={
                'user_name': booking.user.first_name,
                'message_body': f"Unfortunately, {booking.expert.user.get_full_name()} is unavailable for the requested slot. You can explore other experts on Adwise.",
                'expert_name': booking.expert.user.get_full_name(),
                'session_date': booking.slot.date.strftime('%B %d, %Y'),
                'session_time': booking.slot.start_time.strftime('%I:%M %p'),
                'action_url': 'http://127.0.0.1:8000/bookings/search/'
            }
        )
        messages.info(request, "Session request rejected.")

    return redirect('expert_requests')


@login_required
def user_bookings_view(request):
    if request.user.role != UserRole.USER:
        return redirect('expert_dashboard')

    bookings = SessionBooking.objects.filter(user=request.user).select_related('expert__user', 'slot')

    now = timezone.now()
    for b in bookings:
        if b.status == SessionStatus.ACCEPTED and b.payment_deadline and now > b.payment_deadline:
            b.status = SessionStatus.EXPIRED
            b.save()

    return render(request, 'bookings/user_bookings.html', {
        'bookings': bookings,
        'now': now
    })

@login_required
@transaction.atomic
def process_payment_view(request, booking_id):

    booking = get_object_or_404(
        SessionBooking.objects.select_for_update(),
        id=booking_id,
        user=request.user,
        status=SessionStatus.ACCEPTED
    )

    # Check payment deadline
    if booking.is_payment_expired():

        booking.status = SessionStatus.EXPIRED
        booking.save(update_fields=['status'])

        messages.error(
            request,
            "The 24-hour payment window for this session has expired."
        )

        return redirect('user_bookings')

    if request.method == 'POST':

        # ==========================================
        # 1. CONFIRM BOOKING
        # ==========================================

        booking.status = SessionStatus.CONFIRMED

        # ==========================================
        # 2. GENERATE JITSI MEETING LINK
        # ==========================================

        booking.generate_meeting_link()

        # ==========================================
        # 3. LOCK THE SLOT
        # ==========================================

        slot = booking.slot

        slot.is_booked = True
        slot.save(update_fields=['is_booked'])

        # ==========================================
        # 4. REJECT OTHER REQUESTS FOR SAME SLOT
        # ==========================================

        SessionBooking.objects.filter(
            slot=slot,
            status=SessionStatus.REQUESTED
        ).exclude(
            id=booking.id
        ).update(
            status=SessionStatus.REJECTED
        )

        # ==========================================
        # 5. SAVE BOOKING
        # ==========================================

        booking.save(update_fields=['status'])

        # ==========================================
        # 6. CREATE NOTIFICATION FOR EXPERT
        # ==========================================

        create_notification(
            user=booking.expert.user,
            title="Session Confirmed & Meeting Room Ready!",
            message=(
                f"{request.user.get_full_name()} completed payment. "
                f"Your video meeting room is ready."
            )
        )

        # ==========================================
        # 7. SEND EMAIL TO USER
        # ==========================================

        send_session_email_notification(
            recipient_email=booking.user.email,
            subject="Session Confirmed - Your Video Meeting Link",
            template_name='emails/booking_status_email.html',
            context={
                'user_name': booking.user.first_name,

                'message_body': (
                    f"Your session with "
                    f"{booking.expert.user.get_full_name()} "
                    f"is confirmed! You can join the video "
                    f"call using the link below at your "
                    f"scheduled time."
                ),

                'expert_name': (
                    booking.expert.user.get_full_name()
                ),

                'session_date': (
                    slot.date.strftime('%B %d, %Y')
                ),

                'session_time': (
                    f"{slot.start_time.strftime('%I:%M %p')} - "
                    f"{slot.end_time.strftime('%I:%M %p')}"
                ),

                'action_url': booking.meeting_link
            }
        )

        messages.success(
            request,
            "Payment successful! Your consultation session "
            "is now confirmed."
        )

        return redirect('user_bookings')

    return render(
        request,
        'bookings/payment.html',
        {'booking': booking}
    )



@login_required
@transaction.atomic
def respond_postpone_view(request, booking_id, response_action):
    booking = get_object_or_404(
        SessionBooking.objects.select_for_update(), 
        id=booking_id, 
        user=request.user, 
        status=SessionStatus.POSTPONED
    )

    if response_action == 'accept':
        new_slot = ExpertAvailability.objects.create(
            expert=booking.expert,
            date=booking.proposed_date,
            start_time=booking.proposed_start_time,
            end_time=booking.proposed_end_time
        )
        booking.slot = new_slot
        booking.status = SessionStatus.ACCEPTED
        booking.set_payment_deadline()
        booking.save()

        create_notification(
            user=booking.expert.user,
            title="Postponed Time Accepted",
            message=f"{request.user.get_full_name()} accepted your proposed time."
        )
        messages.success(request, "Postponed time accepted! Please proceed to payment within 24 hours.")

    elif response_action == 'decline':
        booking.status = SessionStatus.REJECTED
        booking.save()

        create_notification(
            user=booking.expert.user,
            title="Postponed Time Declined",
            message=f"{request.user.get_full_name()} declined the proposed postponed time."
        )
        messages.info(request, "Postponed offer declined.")

    return redirect('user_bookings')


@login_required
def notifications_view(request):
    user_notifications = Notification.objects.filter(user=request.user)
    user_notifications.filter(is_read=False).update(is_read=True)

    return render(request, 'bookings/notifications.html', {
        'notifications': user_notifications
    })


@login_required
@transaction.atomic
def submit_review_view(request, booking_id):
    booking = get_object_or_404(
        SessionBooking, 
        id=booking_id, 
        user=request.user, 
        status=SessionStatus.CONFIRMED
    )

    # Prevent duplicate reviews for the same session
    if hasattr(booking, 'review'):
        messages.warning(request, "You have already submitted a review for this session.")
        return redirect('user_bookings')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.user = request.user
            review.expert = booking.expert
            review.save()

            messages.success(request, "Thank you! Your feedback has been submitted successfully.")
            return redirect('user_bookings')
    else:
        form = ReviewForm()

    return render(request, 'bookings/submit_review.html', {
        'form': form,
        'booking': booking
    })



def get_subcategories_api(request):
    category_id = request.GET.get('category_id')
    # logic to fetch subcategories...
    return JsonResponse({'subcategories': list(subcategories)})