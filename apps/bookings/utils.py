from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def send_session_email_notification(recipient_email, subject, template_name, context):
    """ Utility function to render HTML templates and send emails safely """
    try:
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=True,  # Prevents app crashing if email dispatch fails
        )
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {recipient_email}: {e}")


def check_and_release_expired_locks():
    """ Automatically expires stale requests (>12h) and unpaid acceptances (>24h) """
    from .models import SessionBooking, SessionStatus
    
    now = timezone.now()

    # 1. Expire unresponded client requests after 12 hours
    twelve_hours_ago = now - timedelta(hours=12)
    stale_requests = SessionBooking.objects.filter(
        status=SessionStatus.REQUESTED,
        created_at__lt=twelve_hours_ago
    )
    for booking in stale_requests:
        booking.status = SessionStatus.EXPIRED
        booking.save(update_fields=['status'])

    # 2. Expire accepted sessions where user failed to pay within 24 hours
    unpaid_accepted = SessionBooking.objects.filter(
        status=SessionStatus.ACCEPTED,
        payment_deadline__lt=now
    )
    for booking in unpaid_accepted:
        booking.status = SessionStatus.EXPIRED
        if booking.slot:
            booking.slot.is_booked = False
            booking.slot.save(update_fields=['is_booked'])
        booking.save(update_fields=['status'])