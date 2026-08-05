from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

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