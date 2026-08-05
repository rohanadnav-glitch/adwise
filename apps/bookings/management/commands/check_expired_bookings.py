from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.bookings.models import SessionBooking, SessionStatus, Notification

class Command(BaseCommand):
    help = 'Checks for unpaid session bookings older than 24 hours and marks them EXPIRED'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        now = timezone.now()
        expired_bookings = SessionBooking.objects.filter(
            status=SessionStatus.ACCEPTED,
            payment_deadline__lt=now
        )

        count = expired_bookings.count()

        for booking in expired_bookings:
            booking.status = SessionStatus.EXPIRED
            booking.save()

            # Notify User
            Notification.objects.create(
                user=booking.user,
                title="Session Booking Expired",
                message=f"Your booking request with {booking.expert.user.get_full_name()} expired because payment was not completed within 24 hours."
            )

            # Notify Expert
            Notification.objects.create(
                user=booking.expert.user,
                title="Pending Request Expired",
                message=f"The session request from {booking.user.get_full_name()} expired due to unpaid status within 24 hours. Your slot is available again."
            )

        self.stdout.write(self.style.SUCCESS(f"Successfully processed and expired {count} unpaid bookings."))