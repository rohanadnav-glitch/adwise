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
from datetime import datetime, timedelta, time
from .utils import send_session_email_notification, check_and_release_expired_locks
from django.db.models import Count, Q, FloatField
from django.db.models.functions import Coalesce


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
# 2. EXPERT SCHEDULE MANAGEMENT & CALENDAR
# ==========================================

@login_required
def schedule_manager_view(request):
    """ Allows experts to set availability via explicit Start Time & End Time with flexible minute-chunking """
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access restricted to Expert accounts.")
        return redirect('accounts:user_dashboard')

    expert_profile = get_object_or_404(ExpertProfile, user=request.user)

    if request.method == 'POST':
        slot_type = request.POST.get('slot_type', 'one_time')
        specific_date_str = request.POST.get('date')
        day_of_week = request.POST.get('day_of_week')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        chunk_minutes = request.POST.get('chunk_minutes', 'none')

        now = timezone.now()
        today = now.date()

        if start_time_str and end_time_str:
            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()

                if start_time >= end_time:
                    messages.error(request, "End time must be strictly after start time.")
                    return redirect('bookings:schedule_manager')

                # Past date/time checks & target parsing
                if slot_type == 'one_time' and specific_date_str:
                    target_date = datetime.strptime(specific_date_str, '%Y-%m-%d').date()
                    if target_date < today:
                        messages.error(request, "You cannot add availability slots for past dates.")
                        return redirect('bookings:schedule_manager')
                    
                    if target_date == today and start_time <= now.time():
                        messages.error(request, "You cannot add availability slots for a past time today.")
                        return redirect('bookings:schedule_manager')
                    target_dow = None
                else:
                    target_date = None
                    target_dow = int(day_of_week) if day_of_week is not None and day_of_week != '' else None

                dummy_date = target_date if target_date else today
                current_start_dt = datetime.combine(dummy_date, start_time)
                total_end_dt = datetime.combine(dummy_date, end_time)

                is_rec = (slot_type == 'recurring')

                created_count = 0
                skipped_count = 0

                # Determine the intervals to check/create
                intervals = []
                if chunk_minutes == 'none':
                    intervals.append((current_start_dt.time(), total_end_dt.time()))
                else:
                    step = int(chunk_minutes)
                    temp_start = current_start_dt
                    while temp_start + timedelta(minutes=step) <= total_end_dt:
                        temp_end = temp_start + timedelta(minutes=step)
                        intervals.append((temp_start.time(), temp_end.time()))
                        temp_start = temp_end

                # Process each interval safely checking ONLY for exact matching duplicate slots
                for s_time, e_time in intervals:
                    slot_query = Q(expert=expert_profile, is_recurring=is_rec)
                    
                    if target_date:
                        slot_query &= Q(date=target_date)
                    else:
                        slot_query &= Q(date__isnull=True)

                    if target_dow is not None:
                        slot_query &= Q(day_of_week=target_dow)
                    else:
                        slot_query &= Q(day_of_week__isnull=True)

                    # Check for an EXACT duplicate slot match (same start and end time)
                    slot_query &= Q(start_time=s_time, end_time=e_time)

                    overlapping_slots = ExpertAvailability.objects.filter(slot_query)

                    if not overlapping_slots.exists():
                        ExpertAvailability.objects.create(
                            expert=expert_profile,
                            is_recurring=is_rec,
                            day_of_week=target_dow,
                            date=target_date,
                            start_time=s_time,
                            end_time=e_time,
                            is_booked=False
                        )
                        created_count += 1
                    else:
                        skipped_count += 1

                # Feedback messages
                if created_count > 0:
                    msg = f"{created_count} availability slot(s) created successfully!"
                    if skipped_count > 0:
                        msg += f" ({skipped_count} duplicate slot(s) were skipped.)"
                    messages.success(request, msg)
                else:
                    messages.info(request, "Selected time slot(s) already exist on your schedule.")

                return redirect('bookings:schedule_manager')
            except ValueError:
                messages.error(request, "Invalid time or date format.")
        else:
            messages.error(request, "Please specify valid start and end times.")

    context = {
        'expert_profile': expert_profile,
    }
    return render(request, 'bookings/schedule_manager.html', context)

@login_required
def delete_slot_view(request, slot_id):
    """ AJAX endpoint / standard view to remove availability slot """
    if request.user.role != UserRole.EXPERT:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Access denied.'}, status=403)
        messages.error(request, "Access denied.")
        return redirect('accounts:user_dashboard')

    slot = get_object_or_404(ExpertAvailability, id=slot_id, expert__user=request.user)

    if slot.is_booked:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Cannot delete a slot that has already been booked.'}, status=400)
        messages.error(request, "Cannot delete a slot that has already been booked.")
    else:
        slot.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Availability slot removed successfully.'})
        messages.success(request, "Availability slot removed successfully.")

    return redirect('bookings:schedule_manager')


@login_required
def get_expert_calendar_events_api(request):
    """ Provides JSON event feed with distinct color-coding for Requested, Accepted, and Paid states """
    if request.user.role != UserRole.EXPERT:
        return JsonResponse([], safe=False)

    expert_profile = get_object_or_404(ExpertProfile, user=request.user)
    events = []
    
    now = timezone.now()
    today = now.date()
    current_time = now.time()

    # 1. Fetch active booking slot IDs
    booked_slot_ids = SessionBooking.objects.filter(
        expert=expert_profile,
        status__in=[SessionStatus.CONFIRMED, SessionStatus.ACCEPTED, SessionStatus.REQUESTED]
    ).values_list('slot_id', flat=True)

    # 2. Fetch Availability Slots (excluding slots with active requests/bookings)
    slots = ExpertAvailability.objects.filter(expert=expert_profile).exclude(id__in=booked_slot_ids)
    
    for slot in slots:
        if slot.is_recurring and slot.day_of_week is not None:
            fc_day = (slot.day_of_week + 1) % 7
            events.append({
                'id': str(slot.id),
                'title': f"Available (Every {slot.get_day_of_week_display()})",
                'startTime': slot.start_time.strftime('%H:%M:%S'),
                'endTime': slot.end_time.strftime('%H:%M:%S'),
                'daysOfWeek': [fc_day],
                'backgroundColor': '#0d6efd',
                'borderColor': '#0d6efd',
                'extendedProps': {'is_booked': False, 'slot_id': slot.id, 'is_past': False}
            })
        elif slot.date:
            is_past_slot = (slot.date < today) or (slot.date == today and slot.end_time <= current_time)
            title_text = "Expired Slot" if is_past_slot else "Available Slot"
            bg_color = "#6c757d" if is_past_slot else "#0d6efd"

            events.append({
                'id': str(slot.id),
                'title': title_text,
                'start': f"{slot.date.isoformat()}T{slot.start_time.strftime('%H:%M:%S')}",
                'end': f"{slot.date.isoformat()}T{slot.end_time.strftime('%H:%M:%S')}",
                'backgroundColor': bg_color,
                'borderColor': bg_color,
                'extendedProps': {
                    'is_booked': False, 
                    'slot_id': slot.id, 
                    'is_past': is_past_slot
                }
            })

    # 3. Fetch Booked / Requested Client Sessions
    bookings = SessionBooking.objects.filter(
        expert=expert_profile, 
        status__in=[SessionStatus.CONFIRMED, SessionStatus.ACCEPTED, SessionStatus.REQUESTED]
    ).select_related('user', 'slot')

    for b in bookings:
        session_date = b.proposed_date or (b.slot.date if (b.slot and b.slot.date) else None)
        start_time = b.slot.start_time if b.slot else b.proposed_start_time
        end_time = b.slot.end_time if b.slot else b.proposed_end_time

        if not session_date or not start_time or not end_time:
            continue

        is_past_booking = (session_date < today) or (session_date == today and end_time <= current_time)
        client_name = b.user.get_full_name().strip() or b.user.username

        # Status & Color Mapping
        if is_past_booking:
            title_text = f"Completed: {client_name}"
            bg_color = "#495057" # Dark Charcoal
            text_color = "#ffffff"
        elif b.status == SessionStatus.CONFIRMED:
            title_text = f"Paid: {client_name}"
            bg_color = "#198754" # Green
            text_color = "#ffffff"
        elif b.status == SessionStatus.ACCEPTED:
            title_text = f"Payment Pending: {client_name}"
            bg_color = "#ffc107" # Yellow
            text_color = "#000000"
        else: # SessionStatus.REQUESTED
            title_text = f"New Request: {client_name}"
            bg_color = "#fd7e14" # Orange
            text_color = "#ffffff"

        events.append({
            'id': f"booking_{b.id}",
            'title': title_text,
            'start': f"{session_date.isoformat()}T{start_time.strftime('%H:%M:%S')}",
            'end': f"{session_date.isoformat()}T{end_time.strftime('%H:%M:%S')}",
            'backgroundColor': bg_color,
            'borderColor': bg_color,
            'textColor': text_color,
            'extendedProps': {
                'is_booked': True,
                'booking_id': b.id,
                'status_code': b.status,
                'is_past': is_past_booking,
                'client_name': client_name,
                'client_email': b.user.email,
                'payment_status': b.get_status_display(),
                'meeting_link': b.meeting_link or '',
                'session_date': session_date.strftime('%b %d, %Y'),
                'session_time': f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
            }
        })

    return JsonResponse(events, safe=False)


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

    # 1. Base database query with ranking annotations and availability check
    raw_experts = ExpertProfile.objects.select_related(
        'user', 'category', 'subcategory', 'state', 'district', 'city'
    ).prefetch_related('subcategories').annotate(
        score=(
            Coalesce('cached_average_rating', 0.0, output_field=FloatField()) * 20 +
            Coalesce('total_sessions_completed', 0.0, output_field=FloatField()) * 2 +
            Coalesce('experience_years', 0.0, output_field=FloatField()) * 4
        )
    ).filter(is_available=True)

    # Apply all search filters to raw_experts
    if query:
        raw_experts = raw_experts.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(qualification__icontains=query) |
            Q(bio__icontains=query) |
            Q(subcategories__name__icontains=query)
        ).distinct()

    if category_id and category_id.isdigit():
        raw_experts = raw_experts.filter(category_id=category_id)
        
    if subcategory_id and subcategory_id.isdigit():
        raw_experts = raw_experts.filter(
            Q(subcategory_id=subcategory_id) | Q(subcategories__id=subcategory_id)
        ).distinct()

    if state_id and state_id.isdigit():
        raw_experts = raw_experts.filter(state_id=state_id)
    if district_id and district_id.isdigit():
        raw_experts = raw_experts.filter(district_id=district_id)
    if city_id and city_id.isdigit():
        raw_experts = raw_experts.filter(city_id=city_id)

    if max_fee:
        try:
            raw_experts = raw_experts.filter(hourly_rate__lte=float(max_fee))
        except ValueError:
            pass

    # 5. PROFESSIONAL DATE FILTER LOGIC
    parsed_date = None
    if selected_date and selected_date != 'None':
        try:
            # Convert string to Date object
            search_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            target_dow = search_date.weekday() # 0 = Monday, 6 = Sunday
            parsed_date = search_date

            # Filter for either a specific unbooked date OR a recurring unbooked day_of_week
            raw_experts = raw_experts.filter(
                Q(availabilities__is_booked=False) &
                (
                    Q(availabilities__date=search_date) |
                    Q(availabilities__is_recurring=True, availabilities__day_of_week=target_dow)
                )
            ).distinct()
        except ValueError:
            pass

    today = timezone.now().date()

    # 2. Python-level Post-Filtering: Keep ONLY experts who have genuinely active/future open slots
    experts = []
    for exp in raw_experts:
        # Check if the expert has any unbooked slots that are either recurring or scheduled for today/future
        has_valid_open_slots = exp.availabilities.filter(
            is_booked=False
        ).filter(
            Q(date__gte=today) | Q(is_recurring=True)
        ).exists()

        if has_valid_open_slots:
            experts.append(exp)

    # 3. Sort final list by score descending (highest ranking score first)
    experts.sort(key=lambda x: x.score, reverse=True)

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
        'parsed_date': parsed_date,
    }
    return render(request, 'bookings/search_results.html', context)


@login_required
def expert_detail_view(request, expert_id):
    expert = get_object_or_404(
        ExpertProfile.objects.select_related('user', 'category', 'subcategory', 'state', 'district', 'city'),
        id=expert_id
    )

    now = timezone.now()
    today = now.date()

    # 1. Expire stale locks in batch
    check_and_release_expired_locks()

    # 2. Fetch raw unbooked slots OR any recurring slots (prevents recurring slots from vanishing)
    all_raw_slots = list(ExpertAvailability.objects.filter(
        Q(expert=expert) & (Q(is_booked=False) | Q(is_recurring=True))
    ).order_by('start_time'))

    # 3. Fetch active sessions with exact dates
    active_bookings = SessionBooking.objects.filter(
        expert=expert,
        status__in=[SessionStatus.REQUESTED, SessionStatus.ACCEPTED, SessionStatus.CONFIRMED]
    ).select_related('slot')

    # Build lookup dictionaries keyed by (slot_id, session_date)
    confirmed_set = set()
    my_bookings_map = {}
    locked_set = set()

    for b in active_bookings:
        b_date = b.proposed_date or (b.slot.date if b.slot else None)
        if not b_date:
            continue

        key = (b.slot_id, b_date)
        if request.user.is_authenticated and b.user_id == request.user.id:
            # Save my booking states specifically
            my_bookings_map[key] = {'status': b.status, 'id': b.id}
        else:
            # Handle other users' slots
            if b.status == SessionStatus.CONFIRMED:
                confirmed_set.add(key)
            elif b.status in (SessionStatus.REQUESTED, SessionStatus.ACCEPTED):
                locked_set.add(key)

    available_slots = []

    # 4. Resolve slots for upcoming 14 calendar days
    for day_offset in range(14):
        target_date = today + timedelta(days=day_offset)
        target_dow = target_date.weekday()

        for slot in all_raw_slots:
            slot_key = (slot.id, target_date)

            # Skip slots already confirmed and paid for by someone else
            if slot_key in confirmed_set:
                continue

            is_valid_slot = False
            if not slot.is_recurring and slot.date == target_date:
                is_valid_slot = True
            elif slot.is_recurring and slot.day_of_week == target_dow:
                is_valid_slot = True

            if is_valid_slot:
                my_booking = my_bookings_map.get(slot_key)
                
                # Flag to check if the session time has passed today
                is_past = (target_date == today and slot.end_time <= now.time())
                
                # Normally we hide past slots today, but if the current user booked it, keep it visible to show "Expired/Completed"
                if target_date == today and slot.start_time <= now.time() and not my_booking:
                    continue

                is_locked = (slot_key in locked_set) and not my_booking

                available_slots.append({
                    'id': slot.id,
                    'date': target_date,
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'my_booking_status': my_booking['status'] if my_booking else None,
                    'my_booking_id': my_booking['id'] if my_booking else None,
                    'is_locked': is_locked,
                    'is_past': is_past,
                })

    available_slots.sort(key=lambda x: (x['date'], x['start_time']))

    return render(request, 'bookings/expert_detail.html', {
        'expert': expert,
        'available_slots': available_slots
    })


@login_required
@transaction.atomic
def process_payment_view(request, booking_id):

    # 1. Fetch the booking without the strict 'ACCEPTED' filter
    booking = get_object_or_404(
        SessionBooking.objects.select_for_update(),
        id=booking_id,
        user=request.user
    )

    # 2. Prevent 404 crashes on double-clicks or page reloads
    if booking.status == SessionStatus.CONFIRMED:
        messages.info(request, "Payment was already successful for this session.")
        return redirect('bookings:user_bookings')

    if booking.status != SessionStatus.ACCEPTED:
        messages.error(request, "This session cannot be paid for at this time.")
        return redirect('bookings:user_bookings')

    # 3. Check payment deadline
    if booking.payment_deadline and timezone.now() > booking.payment_deadline:
        booking.status = SessionStatus.EXPIRED
        booking.save(update_fields=['status'])
        messages.error(request, "The 24-hour payment window for this session has expired.")
        return redirect('bookings:user_bookings')

    if request.method == 'POST':
        import uuid
        booking.status = SessionStatus.CONFIRMED
        
        
        # Generate the CUSTOM internal meeting link
        unique_room_id = f"adwise-room-{booking.id}-{uuid.uuid4().hex[:8]}"
        
        # Point to your newly created videocall app
        booking.meeting_link = f"/call/{unique_room_id}/"

        slot = booking.slot
        # Only lock out the master slot if it is a ONE-TIME slot
        if not slot.is_recurring:
            slot.is_booked = True
            slot.save(update_fields=['is_booked'])

        SessionBooking.objects.filter(
            slot=slot,
            status=SessionStatus.REQUESTED
        ).exclude(
            id=booking.id
        ).update(
            status=SessionStatus.REJECTED
        )

        # Save both the new status and the generated meeting link
        booking.save(update_fields=['status', 'meeting_link'])

        create_notification(
            user=booking.expert.user,
            title="Session Confirmed & Meeting Room Ready!",
            message=f"{request.user.get_full_name()} completed payment. Your video meeting room is ready."
        )

        effective_date = booking.proposed_date or (slot.date if slot else None)
        session_date_str = effective_date.strftime('%B %d, %Y') if effective_date else "Scheduled Date"

        send_session_email_notification(
            recipient_email=booking.user.email,
            subject="Session Confirmed - Your Video Meeting Link",
            template_name='emails/booking_status_email.html',
            context={
                'user_name': booking.user.first_name,
                'message_body': f"Your session with {booking.expert.user.get_full_name()} is confirmed! You can join the video call using the link below at your scheduled time.",
                'expert_name': booking.expert.user.get_full_name(),
                'session_date': session_date_str,
                'session_time': f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}",
                'action_url': booking.meeting_link
            }
        )

        messages.success(request, "Payment successful! Your consultation session is now confirmed.")
        return redirect('bookings:user_bookings')

    return render(request, 'bookings/payment.html', {'booking': booking})


# ==========================================
# 4. USER: REQUEST SESSION & BOOKINGS
# ==========================================
@login_required
@transaction.atomic
def request_session_view(request, slot_id=None):
    """ Standard Single-Slot or Multi-Slot request handler with Exact Date mapping """
    if request.user.role != UserRole.USER:
        messages.error(request, "Only registered users can request expert sessions.")
        return redirect('bookings:search_experts')

    if request.method == 'POST':
        # Captures values like "5" or "5|2026-08-26"
        raw_slot_data = request.POST.getlist('selected_slots')
        title = request.POST.get('request_title', '').strip()
        description = request.POST.get('request_description', '').strip()

        # If accessed via single-slot form POST without checkboxes
        if not raw_slot_data and slot_id:
            passed_date = request.POST.get('slot_date')
            if passed_date:
                raw_slot_data = [f"{slot_id}|{passed_date}"]
            else:
                raw_slot_data = [str(slot_id)]

        if not raw_slot_data:
            messages.error(request, "Please select at least one consultation slot.")
            return redirect('bookings:search_experts')

        created_count = 0
        expert_user = None
        today = timezone.now().date()

        for item in raw_slot_data:
            # Parse the ID and the specific Date sent from the frontend
            if '|' in item:
                sid, date_str = item.split('|')
                # Lock the exact date the user clicked on the calendar
                target_booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                sid = item
                target_booking_date = None

            slot = get_object_or_404(
                ExpertAvailability.objects.select_for_update(), 
                id=sid, 
                is_booked=False
            )
            expert_user = slot.expert.user

            # Fallback: If no date was passed, safely calculate the next valid occurrence
            if not target_booking_date:
                if slot.is_recurring and slot.day_of_week is not None:
                    days_ahead = (slot.day_of_week - today.weekday()) % 7
                    target_booking_date = today + timedelta(days=days_ahead)
                    # If time has passed today, move to next week
                    if target_booking_date < today:
                        target_booking_date += timedelta(days=7)
                else:
                    target_booking_date = slot.date

            # Ensure this exact slot + date combination isn't already requested by this user
            existing_request = SessionBooking.objects.filter(
                user=request.user, 
                slot=slot, 
                proposed_date=target_booking_date,
                status__in=[SessionStatus.REQUESTED, SessionStatus.ACCEPTED, SessionStatus.CONFIRMED]
            ).exists()

            if not existing_request:
                SessionBooking.objects.create(
                    user=request.user,
                    expert=slot.expert,
                    slot=slot,
                    proposed_date=target_booking_date,
                    title=title,
                    description=description,
                    status=SessionStatus.REQUESTED
                )
                created_count += 1

        if created_count > 0 and expert_user:
            create_notification(
                user=expert_user,
                title="New Session Request Received",
                message=f"{request.user.get_full_name()} sent {created_count} consultation request(s): '{title}'."
            )
            messages.success(request, f"{created_count} session request(s) sent to the expert!")
        else:
            messages.warning(request, "You already have active requests for the selected slot(s).")

        return redirect('bookings:user_bookings')

    # Default GET fallback redirect
    if slot_id:
        slot = get_object_or_404(ExpertAvailability, id=slot_id)
        return redirect('bookings:expert_detail', expert_id=slot.expert.id)
    return redirect('bookings:search_experts')


@login_required
def expert_requests_view(request):
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access restricted to Expert accounts.")
        return redirect('accounts:user_dashboard')

    expert = get_object_or_404(ExpertProfile, user=request.user)
    requests_list = SessionBooking.objects.filter(expert=expert).select_related('user', 'slot')

    # FIX: Use local machine time instead of UTC to match your saved slots
    from datetime import datetime
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    # Determine if the session time has passed for the expert's dashboard
    for req in requests_list:
        session_date = req.proposed_date or (req.slot.date if (req.slot and req.slot.date) else None)
        end_time = req.proposed_end_time or (req.slot.end_time if req.slot else None)

        if session_date and end_time:
            req.is_past = (session_date < today) or (session_date == today and end_time <= current_time)
        else:
            req.is_past = False

    return render(request, 'bookings/expert_requests.html', {
        'requests_list': requests_list
    })


@login_required
@transaction.atomic
def expert_action_view(request, booking_id, action):
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access denied.")
        return redirect('accounts:user_dashboard')

    booking = get_object_or_404(
        SessionBooking.objects.select_for_update(), 
        id=booking_id, 
        expert__user=request.user
    )

    if action == 'accept':
        booking.status = SessionStatus.ACCEPTED
        booking.payment_deadline = timezone.now() + timedelta(hours=24)
        booking.save()

        create_notification(
            user=booking.user,
            title="Session Request Accepted!",
            message=f"{booking.expert.user.get_full_name()} accepted your request. Complete payment within 24 hours."
        )

        effective_date = booking.proposed_date or (booking.slot.date if booking.slot else None)
        session_date_str = effective_date.strftime('%B %d, %Y') if effective_date else "Scheduled Date"
        session_time_str = f"{booking.slot.start_time.strftime('%I:%M %p')} - {booking.slot.end_time.strftime('%I:%M %p')}" if booking.slot and hasattr(booking.slot, 'start_time') else "Scheduled Time"

        send_session_email_notification(
            recipient_email=booking.user.email,
            subject="Action Required: Your Adwise Session Request is Accepted!",
            template_name='emails/booking_status_email.html',
            context={
                'user_name': booking.user.first_name,
                'message_body': f"Great news! {booking.expert.user.get_full_name()} has accepted your consultation request. Please log in and complete your payment within 24 hours to secure your slot.",
                'expert_name': booking.expert.user.get_full_name(),
                'session_date': session_date_str,
                'session_time': session_time_str,
                'action_url': 'http://127.0.0.1:8000/bookings/my-bookings/'
            }
        )
        messages.success(request, "Request accepted and notification email sent to user.")

    elif action == 'reject':
        rejection_reason = request.POST.get('rejection_reason', 'The expert is unavailable at this time.').strip()
        booking.status = SessionStatus.REJECTED
        booking.save()

        create_notification(
            user=booking.user,
            title="Session Request Update",
            message=f"{booking.expert.user.get_full_name()} declined your request. Reason: {rejection_reason}"
        )

        effective_date = booking.proposed_date or (booking.slot.date if booking.slot else None)
        session_date_str = effective_date.strftime('%B %d, %Y') if effective_date else "Scheduled Date"
        session_time_str = booking.slot.start_time.strftime('%I:%M %p') if booking.slot and hasattr(booking.slot, 'start_time') else "Scheduled Time"

        send_session_email_notification(
            recipient_email=booking.user.email,
            subject="Update on your Adwise Session Request",
            template_name='emails/booking_status_email.html',
            context={
                'user_name': booking.user.first_name,
                'message_body': f"Unfortunately, {booking.expert.user.get_full_name()} was unable to accept your request. Reason provided: {rejection_reason}",
                'expert_name': booking.expert.user.get_full_name(),
                'session_date': session_date_str,
                'session_time': session_time_str,
                'action_url': 'http://127.0.0.1:8000/bookings/search/'
            }
        )
        messages.info(request, "Session request rejected.")

    elif action == 'postpone':
        proposed_date_str = request.POST.get('proposed_date')
        proposed_start_str = request.POST.get('proposed_start_time')
        proposed_end_str = request.POST.get('proposed_end_time')

        if proposed_date_str and proposed_start_str and proposed_end_str:
            p_date = datetime.strptime(proposed_date_str, '%Y-%m-%d').date()
            p_start = datetime.strptime(proposed_start_str, '%H:%M').time()
            p_end = datetime.strptime(proposed_end_str, '%H:%M').time()

            conflict_exists = ExpertAvailability.objects.filter(
                expert=booking.expert,
                date=p_date,
                start_time=p_start,
                end_time=p_end,
                is_booked=True
            ).exists()

            if conflict_exists:
                messages.error(request, "Cannot postpone: You already have a confirmed booking at that proposed date and time.")
                return redirect('bookings:expert_requests')

            booking.proposed_date = p_date
            booking.proposed_start_time = p_start
            booking.proposed_end_time = p_end
            booking.status = SessionStatus.POSTPONED
            booking.save()

            create_notification(
                user=booking.user,
                title="Session Postponement Proposal",
                message=f"{booking.expert.user.get_full_name()} proposed a new session time: {p_date.strftime('%b %d, %Y')} at {p_start.strftime('%I:%M %p')}."
            )
            messages.success(request, "Postponement proposal sent to the user.")

    return redirect('bookings:expert_requests')


@login_required
def user_bookings_view(request):
    if request.user.role != UserRole.USER:
        return redirect('accounts:expert_dashboard')

    check_and_release_expired_locks()

    bookings = SessionBooking.objects.filter(user=request.user).select_related('expert__user', 'slot')
    
    # FIX: Use local machine time instead of UTC to match your saved slots
    from datetime import datetime
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    # Determine if the session is completely over to unlock the review feature
    for b in bookings:
        session_date = b.proposed_date or (b.slot.date if (b.slot and b.slot.date) else None)
        end_time = b.proposed_end_time or (b.slot.end_time if b.slot else None)

        if session_date and end_time:
            b.is_past = (session_date < today) or (session_date == today and end_time <= current_time)
        else:
            b.is_past = False

    return render(request, 'bookings/user_bookings.html', {
        'bookings': bookings,
        'now': now
    })

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
        booking.payment_deadline = timezone.now() + timedelta(hours=24)
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

    return redirect('bookings:user_bookings')


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

    if hasattr(booking, 'review'):
        messages.warning(request, "You have already submitted a review for this session.")
        return redirect('bookings:user_bookings')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.user = request.user
            review.expert = booking.expert
            review.save()

            messages.success(request, "Thank you! Your feedback has been submitted successfully.")
            return redirect('bookings:user_bookings')
    else:
        form = ReviewForm()

    return render(request, 'bookings/submit_review.html', {
        'form': form,
        'booking': booking
    })


def get_subcategories_api(request):
    category_id = request.GET.get('category_id')
    subcategories = []
    
    if category_id and category_id.isdigit():
        from apps.categories.models import Subcategory
        subcategories = Subcategory.objects.filter(category_id=category_id).values('id', 'name')
        
    return JsonResponse({'subcategories': list(subcategories)})