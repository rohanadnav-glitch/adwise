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
    
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def average_rating(self):
        result = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(result, 1) if result else 0.0

    @property
    def total_reviews_count(self):
        return self.reviews.count()

    def __str__(self):
        return f"ExpertProfile: {self.user.get_full_name() or self.user.username}"