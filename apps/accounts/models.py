from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.locations.models import State, District, City
from apps.categories.models import Category, SubCategory
from django.db.models import Avg, Count


class UserRole(models.TextChoices):
    USER = 'USER', 'User'
    EXPERT = 'EXPERT', 'Expert'


class CustomUser(AbstractUser):
    role = models.CharField(
        max_length=10, 
        choices=UserRole.choices, 
        default=UserRole.USER,
        db_index=True
    )
    phone_number = models.CharField(max_length=15, unique=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def is_expert(self):
        return self.role == UserRole.EXPERT

    def is_regular_user(self):
        return self.role == UserRole.USER

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='user_profile')
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"UserProfile: {self.user.username}"


class ExpertProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='expert_profile')
    
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True)
    subcategories = models.ManyToManyField(SubCategory, related_name='expert_profiles', blank=True)
    
    qualification = models.CharField(max_length=255)
    experience_years = models.PositiveIntegerField(default=0)
    
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True)
    
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    bio = models.TextField(blank=True)
    
    # Documents, Socials, & Contact
    resume = models.FileField(upload_to='resumes/', null=True, blank=True)
    certificate = models.FileField(upload_to='certificates/', null=True, blank=True)
    
    linkedin_url = models.URLField(max_length=255, null=True, blank=True)
    instagram_url = models.URLField(max_length=255, null=True, blank=True)
    facebook_url = models.URLField(max_length=255, null=True, blank=True)
    
    whatsapp_number = models.CharField(max_length=15, null=True, blank=True)
    
    # Availability & Metrics
    is_available = models.BooleanField(default=True)
    availability_toggled_at = models.DateTimeField(null=True, blank=True)
    
    total_sessions_completed = models.PositiveIntegerField(default=0)
    cached_average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)

    # Checkbox field
    share_whatsapp_with_clients = models.BooleanField(
        default=False, 
        help_text="Allow booked clients to see your WhatsApp number"
    )

    # Update profile_completion_score to check certificates list or model
    @property
    def profile_completion_score(self):
        has_certificate = self.certificates.exists() or bool(self.certificate)
        fields_to_check = [
            bool(self.user.first_name and self.user.last_name),
            bool(self.profile_picture),
            bool(self.bio),
            bool(self.qualification),
            bool(self.experience_years is not None),
            bool(self.hourly_rate and self.hourly_rate > 0),
            bool(self.resume),
            bool(has_certificate),
            bool(self.state and self.district and self.city),
            bool(self.linkedin_url or self.instagram_url or self.facebook_url),
        ]
        filled = sum(1 for field in fields_to_check if field)
        return int((filled / len(fields_to_check)) * 100)


# Model for handling multiple certificates
class ExpertCertificate(models.Model):
    expert = models.ForeignKey(ExpertProfile, on_delete=models.CASCADE, related_name='certificates')
    file = models.FileField(upload_to='certificates/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate for {self.expert.user.username}"

    @property
    def average_rating(self):
        if hasattr(self, 'reviews'):
            result = self.reviews.aggregate(avg=Avg('rating'))['avg']
            return round(result, 1) if result else 0.0
        return 0.0

    @property
    def total_reviews_count(self):
        if hasattr(self, 'reviews'):
            return self.reviews.count()
        return 0

    @property
    def profile_completion_score(self):
        fields_to_check = [
            bool(self.user.first_name and self.user.last_name),
            bool(self.profile_picture),
            bool(self.bio),
            bool(self.qualification),
            bool(self.experience_years is not None),
            bool(self.hourly_rate and self.hourly_rate > 0),
            bool(self.resume),
            bool(self.certificate),
            bool(self.state and self.district and self.city),
            bool(self.linkedin_url or self.instagram_url or self.facebook_url),
        ]
        
        filled = sum(1 for field in fields_to_check if field)
        total = len(fields_to_check)
        return int((filled / total) * 100)
    

    def __str__(self):
        return f"ExpertProfile: {self.user.get_full_name() or self.user.username}"