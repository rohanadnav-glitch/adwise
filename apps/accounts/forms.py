import re
from django import forms
from django.contrib.auth import get_user_model
from decimal import Decimal
# Import models directly, NOT views
from .models import UserRole, ExpertProfile, CustomUser 
from apps.categories.models import Category, SubCategory
from apps.locations.models import State, District, City



User = get_user_model()


# ==========================================
# 1. USER REGISTRATION FORM
# ==========================================
class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'First Name',
            'id': 'id_first_name'  # explicitly setting ID for JS selection
        })
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Last Name',
            'id': 'id_last_name'  # Added ID for JavaScript selection
        })
    )



    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Email Address',
            'id': 'id_email'  # Explicit ID for JS selection
        })
    )

    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Phone Number',
            'id': 'id_phone_number',
            'maxlength': '10'  # Prevents typing more than 10 digits
        })
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
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password',
            'id': 'id_password'
        })
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Confirm Password',
            'id': 'id_confirm_password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        return cleaned_data

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()

        if not first_name:
            raise forms.ValidationError("First name is required.")

        # Allows only letters, spaces, hyphens, and apostrophes
        if not re.match(r"^[A-Za-z'-]+$", first_name):
            raise forms.ValidationError("First name must contain only letters.")

        if len(first_name) < 2:
            raise forms.ValidationError("First name must be at least 2 characters long.")

        return first_name.capitalize()

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()

        if not last_name:
            raise forms.ValidationError("Last name is required.")

        # Allows letters, hyphens, and apostrophes
        if not re.match(r"^[A-Za-z'-]+$", last_name):
            raise forms.ValidationError("Last name must contain only letters.")

        if len(last_name) < 2:
            raise forms.ValidationError("Last name must be at least 2 characters long.")

        return last_name.capitalize()
    

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()

        if not email:
            raise forms.ValidationError("Email address is required.")

        # Standard Email Format Check
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Please enter a valid email address.")

        # Check if email is already registered in the database
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")

        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number', '').strip()

        if not phone_number:
            raise forms.ValidationError("Phone number is required.")

        # Ensure exactly 10 digits
        if not re.match(r"^\d{10}$", phone_number):
            raise forms.ValidationError("Phone number must be exactly 10 digits.")

        # Ensure valid Indian mobile start digit (6, 7, 8, or 9)
        if not re.match(r"^[6-9]", phone_number):
            raise forms.ValidationError("Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9.")

        return phone_number

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Populate querysets dynamically when form data is posted
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

        # 2. Populate querysets if editing an existing instance
        elif self.instance and self.instance.pk:
            if self.instance.state:
                self.fields['district'].queryset = District.objects.filter(state=self.instance.state)
            if self.instance.district:
                self.fields['city'].queryset = City.objects.filter(district=self.instance.district)



    def clean_password(self):
        password = self.cleaned_data.get('password', '')

        if not password:
            raise forms.ValidationError("Password is required.")

        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")

        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least one uppercase letter (A-Z).")

        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must contain at least one lowercase letter (a-z).")

        if not re.search(r'\d', password):
            raise forms.ValidationError("Password must contain at least one digit (0-9).")

        if not re.search(r'[@$!%*?&]', password):
            raise forms.ValidationError("Password must contain at least one special character (@, $, !, %, *, ?, &).")

        return password

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'state', 'district', 'city', 'password']


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User  
        fields = ['first_name', 'last_name', 'phone_number', 'date_of_birth']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ==========================================
# 2. EXPERT REGISTRATION - STEP 1 (Account Info)
# ==========================================
class ExpertStep1Form(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'First Name',
            'id': 'id_first_name'
        })
    )

    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Last Name',
            'id': 'id_last_name'
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Email Address',
            'id': 'id_email'
        })
    )


    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Phone Number',
            'id': 'id_phone_number',
            'maxlength': '10'  # Restricts input length in HTML
        })
    )


    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password',
            'id': 'id_password'
        })
    )


    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Confirm Password',
            'id': 'id_confirm_password'
        })
    )


       

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()

        if not first_name:
            raise forms.ValidationError("First name is required.")
        if len(first_name) < 2:
            raise forms.ValidationError("First name must be at least 2 characters long.")
        if not re.match(r'^[a-zA-Z\s]+$', first_name):
            raise forms.ValidationError("First name can only contain letters and spaces.")

        return first_name.title()  # Capitalizes first letter

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()

        if not last_name:
            raise forms.ValidationError("Last name is required.")
        if len(last_name) < 2:
            raise forms.ValidationError("Last name must be at least 2 characters long.")
        if not re.match(r'^[a-zA-Z\s]+$', last_name):
            raise forms.ValidationError("Last name can only contain letters and spaces.")

        return last_name.title()

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()

        if not email:
            raise forms.ValidationError("Email address is required.")

        # 1. Check for standard email format with common top-level domains (.com, .in, .org, .edu, .net, .co.in, etc.)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(com|in|org|edu|net|gov|co\.in|ac\.in)$'
        if not re.match(email_pattern, email):
            raise forms.ValidationError("Please enter a valid email address (e.g., example@domain.com).")

        # 2. Prevent continuous repeated characters like 'dsfsds' or 'aaaaa' in domain
        domain = email.split('@')[1]
        if re.search(r'(.)\1{3,}', domain):  # Prevents 4 identical consecutive characters
            raise forms.ValidationError("Please enter a valid email domain.")

        # 3. Check if email already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")

        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()

        if not phone:
            raise forms.ValidationError("Phone number is required.")

        # Check for valid 10-digit Indian mobile number format
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise forms.ValidationError("Please enter a valid 10-digit phone number starting with 6, 7, 8, or 9.")

        # Prevent repeated numbers like 9999999999 or 0000000000
        if len(set(phone)) == 1:
            raise forms.ValidationError("Please enter a valid phone number.")

        return phone

    def clean_password(self):
        password = self.cleaned_data.get('password', '')

        if not password:
            raise forms.ValidationError("Password is required.")
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'\d', password):
            raise forms.ValidationError("Password must contain at least one digit.")
        if not re.search(r'[@$!%*?&]', password):
            raise forms.ValidationError("Password must contain at least one special character (@$!%*?&).")

        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if confirm_password and password and confirm_password != password:
            self.add_error('confirm_password', "Passwords do not match.")

        return cleaned_data



# ==========================================
# 3. EXPERT REGISTRATION - STEP 2 (Credentials & Location)
# ==========================================
class ExpertStep2Form(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        empty_label="Select Category",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_category'})
    )
    subcategory = forms.ModelMultipleChoiceField(
        queryset=SubCategory.objects.none(),  # Default to empty until Category is chosen
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'id': 'id_subcategory'})
    )
    qualification = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'e.g. Master of Laws (LL.M)',
            'id': 'id_qualification'
        })
    )
    experience_years = forms.IntegerField(
        min_value=0,
        max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'e.g. 5',
            'id': 'id_experience_years'
        })
    )
    hourly_rate = forms.IntegerField(
        min_value=100,
        max_value=50000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '1',
            'min': '100',
            'max': '50000',
            'placeholder': 'e.g. 1500',
            'id': 'id_hourly_rate'
        })
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
    bio = forms.CharField(
        min_length=50,
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4, 
            'placeholder': 'Tell clients about your expertise...',
            'id': 'id_bio',
            'maxlength': '1000'
        })
    )

    def clean_qualification(self):
        qualification = self.cleaned_data.get('qualification', '').strip()
        if not qualification:
            raise forms.ValidationError("Highest qualification is required.")
        if len(qualification) < 2:
            raise forms.ValidationError("Qualification must be at least 2 characters long.")
        return qualification

    def clean_experience_years(self):
        experience = self.cleaned_data.get('experience_years')
        if experience is None:
            raise forms.ValidationError("Years of experience is required.")
        if experience < 0 or experience > 60:
            raise forms.ValidationError("Please enter a realistic experience value between 0 and 60 years.")
        return experience

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '').strip()

        if not bio:
            raise forms.ValidationError("Professional bio is required.")
        if len(bio) < 50:
            raise forms.ValidationError("Bio must be at least 50 characters long to provide clients sufficient context.")
        if len(bio) > 1000:
            raise forms.ValidationError("Bio cannot exceed 1,000 characters.")

        return bio


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamic queryset filtering upon POST submission
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

        # Dynamic queryset filtering when initializing bound session data
        elif self.initial:
            if self.initial.get('category_id'):
                self.fields['subcategory'].queryset = SubCategory.objects.filter(category_id=self.initial['category_id'])
            if self.initial.get('state_id'):
                self.fields['district'].queryset = District.objects.filter(state_id=self.initial['state_id'])
            if self.initial.get('district_id'):
                self.fields['city'].queryset = City.objects.filter(district_id=self.initial['district_id'])


# ==========================================
# 3. LOGIN FORM
# ==========================================
class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Username or Email Address',
            'id': 'id_username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password',
            'id': 'id_password'
        })
    )


class ExpertProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

    hourly_rate = forms.IntegerField(
        min_value=100,
        max_value=50000,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'id': 'id_hourly_rate'})
    )

    class Meta:
        model = ExpertProfile
        fields = [
            'qualification', 
            'experience_years', 
            'hourly_rate', 
            'bio',
            'profile_picture',
            'resume',
            'certificate',
            'linkedin_url',
            'instagram_url',
            'facebook_url',
            'whatsapp_number'
        ]
        widgets = {
            'qualification': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_qualification'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_experience_years'}),
            'bio': forms.Textarea if hasattr(forms, 'Textarea') else forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'id': 'id_bio'}),
            'resume': forms.FileInput(attrs={'class': 'form-control'}),
            'certificate': forms.FileInput(attrs={'class': 'form-control'}),
            'linkedin_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/in/username'}),
            'instagram_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://instagram.com/username'}),
            'facebook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/username'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'WhatsApp / Emergency Number'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.hourly_rate:
            self.initial['hourly_rate'] = int(self.instance.hourly_rate)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['date_of_birth'].initial = self.instance.user.date_of_birth

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '').strip()
        if not bio:
            raise forms.ValidationError("Professional bio is required.")
        if len(bio) < 50:
            raise forms.ValidationError("Bio must be at least 50 characters long.")
        return bio