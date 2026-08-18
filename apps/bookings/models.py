from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import CustomUser, ExpertProfile
import uuid


from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model



class ExpertAvailability(models.Model):
    DAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )

    expert = models.ForeignKey(
        ExpertProfile, 
        on_delete=models.CASCADE, 
        related_name='availabilities'
    )
    
    # Recurring vs One-time toggle
    is_recurring = models.BooleanField(default=False, db_index=True)
    day_of_week = models.IntegerField(choices=DAY_CHOICES, null=True, blank=True, db_index=True)
    
    # Specific date (Optional if recurring)
    date = models.DateField(null=True, blank=True, db_index=True)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'day_of_week', 'start_time']
        verbose_name_plural = "Expert Availabilities"

    def __str__(self):
        status = "Booked" if self.is_booked else "Available"
        if self.is_recurring and self.day_of_week is not None:
            day_name = dict(self.DAY_CHOICES).get(self.day_of_week)
            return f"{self.expert.user.get_full_name()} | Every {day_name} [{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}] ({status})"
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
    
    # NEW FIELDS: Topic & Note
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    payment_deadline = models.DateTimeField(null=True, blank=True)

    # Postpone Feature Fields
    proposed_date = models.DateField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time = models.TimeField(null=True, blank=True)
    meeting_link = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
   

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