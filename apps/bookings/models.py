from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import CustomUser, ExpertProfile
import uuid


from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model



class ExpertAvailability(models.Model):
    expert = models.ForeignKey(
        ExpertProfile, 
        on_delete=models.CASCADE, 
        related_name='availabilities'
    )
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']
        verbose_name_plural = "Expert Availabilities"
        unique_together = ('expert', 'date', 'start_time')

    def __str__(self):
        status = "Booked" if self.is_booked else "Available"
        return f"{self.expert.user.get_full_name()} | {self.date} [{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}] ({status})"


class SessionStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', 'Requested'
    ACCEPTED = 'ACCEPTED', 'Accepted (Payment Pending)'
    POSTPONED = 'POSTPONED', 'Postponed by Expert'
    CONFIRMED = 'CONFIRMED', 'Confirmed (Paid)'
    REJECTED = 'REJECTED', 'Rejected'
    EXPIRED = 'EXPIRED', 'Expired (Unpaid)'


class SessionBooking(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='bookings'
    )
    expert = models.ForeignKey(
        ExpertProfile, 
        on_delete=models.CASCADE, 
        related_name='sessions'
    )
    slot = models.ForeignKey(
        ExpertAvailability, 
        on_delete=models.CASCADE, 
        related_name='booking_requests'
    )
    status = models.CharField(
        max_length=20, 
        choices=SessionStatus.choices, 
        default=SessionStatus.REQUESTED,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    payment_deadline = models.DateTimeField(null=True, blank=True)

    # Postpone Feature Fields
    proposed_date = models.DateField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time = models.TimeField(null=True, blank=True)
    meeting_link = models.URLField(max_length=500, blank=True, null=True)
    class Meta:
        ordering = ['-created_at']

    def set_payment_deadline(self):
        """ Calculates a 24-hour window from acceptance """
        self.payment_deadline = timezone.now() + timedelta(hours=24)

    def is_payment_expired(self):
        if self.status == SessionStatus.ACCEPTED and self.payment_deadline:
            return timezone.now() > self.payment_deadline
        return False






    def generate_meeting_link(self):
        """Generate a unique, hard-to-guess Jitsi Meet room link."""

        unique_room_id = (
            f"Adwise-Consultation-{self.id}-"
            f"{uuid.uuid4().hex[:10]}"
        )

        self.meeting_link = (
            f"https://meet.jit.si/{unique_room_id}"
        )

        self.save(update_fields=['meeting_link'])

        return self.meeting_link




    def __str__(self):
        return f"Booking #{self.id}: {self.user.username} -> {self.expert.user.username} ({self.get_status_display()})"

    
   

class Notification(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"





User = get_user_model()


class Review(models.Model):
    booking = models.OneToOneField(
        'SessionBooking', 
        on_delete=models.CASCADE, 
        related_name='review'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    expert = models.ForeignKey(ExpertProfile, on_delete=models.CASCADE, related_name='reviews')
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review ({self.rating}★) by {self.user.first_name} for {self.expert.user.first_name}"