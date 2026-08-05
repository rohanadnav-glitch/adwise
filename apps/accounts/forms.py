import re
from django import forms
from django.contrib.auth import get_user_model

# Import models directly, NOT views
from .models import UserRole, ExpertProfile
from apps.categories.models import Category, SubCategory
from apps.locations.models import State, District, City

User = get_user_model()


# ==========================================
# 1. USER REGISTRATION FORM
# ==========================================
class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    state = forms.ModelChoiceField(
        queryset=State.objects.all(),
        required=False,
        empty_label="Select State",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_state'})
    )
    district = forms.ModelChoiceField(
        queryset=District.objects.none(),
        required=False,
        empty_label="Select District",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_district'})
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.none(),
        required=False,
        empty_label="Select City",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_city'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'state', 'district', 'city', 'password']

# ==========================================
# 2. EXPERT REGISTRATION - STEP 1 (Account Info)
# ==========================================
class ExpertStep1Form(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'})
    )

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name.isalpha():
            raise forms.ValidationError("First name must contain only letters.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name.isalpha():
            raise forms.ValidationError("Last name must contain only letters.")
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if not re.match(r'^\+?[0-9]{10,15}$', phone):
            raise forms.ValidationError("Enter a valid phone number (10 to 15 digits).")
        if User.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("A user with this phone number already exists.")
        return phone

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'\d', password):
            raise forms.ValidationError("Password must contain at least one digit.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

# ==========================================
# 3. EXPERT REGISTRATION - STEP 2 (Credentials & Location)
# ==========================================
class ExpertStep2Form(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_category'})
    )
    subcategory = forms.ModelChoiceField(
        queryset=SubCategory.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_subcategory'})
    )
    qualification = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., M.Tech, Ph.D, CA'})
    )
    experience_years = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Years of Experience'})
    )
    hourly_rate = forms.DecimalField(
        min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1000'})
    )
    state = forms.ModelChoiceField(
        queryset=State.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_state'})
    )
    district = forms.ModelChoiceField(
        queryset=District.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_district'})
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_city'})
    )
    bio = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe your professional experience...'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamic querysets for POST validation
        if 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = SubCategory.objects.filter(category_id=category_id)
            except (ValueError, TypeError):
                pass

        if 'state' in self.data:
            try:
                state_id = int(self.data.get('state'))
                self.fields['district'].queryset = District.objects.filter(state_id=state_id)
            except (ValueError, TypeError):
                pass

        if 'district' in self.data:
            try:
                district_id = int(self.data.get('district'))
                self.fields['city'].queryset = City.objects.filter(district_id=district_id)
            except (ValueError, TypeError):
                pass

    def clean_experience_years(self):
        exp = self.cleaned_data.get('experience_years')
        if exp < 0 or exp > 60:
            raise forms.ValidationError("Please enter a realistic number of years of experience.")
        return exp

    def clean_hourly_rate(self):
        rate = self.cleaned_data.get('hourly_rate')
        if rate <= 0:
            raise forms.ValidationError("Consultation fee must be greater than zero.")
        return rate


# ==========================================
# 3. LOGIN FORM
# ==========================================
class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username or Email Address'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class ExpertProfileUpdateForm(forms.ModelForm):
    hourly_rate = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your session fee in ₹',
            'min': '0'
        }),
        help_text="Update your hourly consultation fee (in ₹)"
    )
    qualification = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    experience_years = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
    )
    bio = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )

    class Meta:
        model = ExpertProfile
        fields = ['hourly_rate', 'qualification', 'experience_years', 'bio']



