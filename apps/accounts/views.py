from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout, authenticate
from django.contrib.auth.decorators import login_required
# At the top of apps/accounts/views.py
from .models import CustomUser, UserRole, ExpertProfile

# Imports from forms and models
from .forms import UserRegistrationForm, ExpertStep1Form, ExpertStep2Form, LoginForm
from .models import UserRole, ExpertProfile

# ==========================================
# HELPER: ROLE-BASED ACCESS CONTROL REDIRECT
# ==========================================
def redirect_by_role(user):
    if user.role == UserRole.EXPERT:
        return redirect('expert_dashboard')
    return redirect('user_dashboard')


# ==========================================
# USER REGISTRATION VIEW
# ==========================================
User = get_user_model()

# ==========================================
# USER REGISTRATION VIEW
# ==========================================
def register_user_view(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            
            # Set username to email to prevent UNIQUE constraint collisions
            user.username = form.cleaned_data['email']
            user.set_password(form.cleaned_data['password'])
            
            # Save phone number if field exists on CustomUser model
            if hasattr(user, 'phone_number'):
                user.phone_number = form.cleaned_data.get('phone_number')

            # Assign location fields (State, District, City)
            if hasattr(user, 'state_id'):
                user.state = form.cleaned_data.get('state')
            if hasattr(user, 'district_id'):
                user.district = form.cleaned_data.get('district')
            if hasattr(user, 'city_id'):
                user.city = form.cleaned_data.get('city')
                
            user.role = UserRole.USER
            user.save()

            messages.success(request, "Account created successfully! Please log in with your credentials.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors highlighted below.")
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register_user.html', {'form': form})

# ==========================================
# EXPERT REGISTRATION - STEP 1 VIEW
# ==========================================
def expert_register_step1(request):
    if request.method == 'POST':
        form = ExpertStep1Form(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            
            # Save step 1 data to session (using email as username)
            request.session['expert_wizard_step1'] = {
                'first_name': cleaned['first_name'],
                'last_name': cleaned['last_name'],
                'email': cleaned['email'],
                'username': cleaned['email'],  # Automatically use email as username
                'phone_number': cleaned['phone_number'],
                'password': cleaned['password'],
            }
            request.session.modified = True
            return redirect('expert_register_step2')
        else:
            messages.error(request, "Please fix the errors in Step 1.")
    else:
        initial_data = request.session.get('expert_wizard_step1', {})
        form = ExpertStep1Form(initial=initial_data)

    return render(request, 'accounts/expert_step1.html', {'form': form})


# ==========================================
# EXPERT REGISTRATION - STEP 2 VIEW
# ==========================================
def expert_register_step2(request):
    # 1. Guard check for Step 1
    if 'expert_wizard_step1' not in request.session:
        messages.warning(request, "Please complete Step 1 first.")
        return redirect('expert_register_step1')

    if request.method == 'POST':
        form = ExpertStep2Form(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            
            # Helper function to get primary key safely whether it's a Model instance or PK integer
            def get_id(obj):
                if hasattr(obj, 'id'):
                    return obj.id
                return obj if obj else None

            # Store step 2 data safely
            request.session['expert_wizard_step2'] = {
                'category_id': get_id(cleaned.get('category')),
                'subcategory_id': get_id(cleaned.get('subcategory')),
                'qualification': cleaned.get('qualification', ''),
                'experience_years': cleaned.get('experience_years', 0),
                'hourly_rate': str(cleaned.get('hourly_rate', 0)),
                'state_id': get_id(cleaned.get('state')),
                'district_id': get_id(cleaned.get('district')),
                'city_id': get_id(cleaned.get('city')),
                'bio': cleaned.get('bio', ''),
            }
            
            # Explicitly mark session as modified
            request.session.modified = True
            return redirect('expert_register_step3')
        else:
            messages.error(request, "Please correct the errors in Step 2 below.")
    else:
        initial_data = request.session.get('expert_wizard_step2', {})
        form = ExpertStep2Form(initial=initial_data)

    return render(request, 'accounts/expert_step2.html', {'form': form})


    
# Step 3: Summary Preview & Atomic Commit
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db import transaction

# Model imports
from .models import UserRole, ExpertProfile
from apps.categories.models import Category, SubCategory
from apps.locations.models import State, District, City

User = get_user_model()


def expert_register_step3(request):
    step1 = request.session.get('expert_wizard_step1')
    step2 = request.session.get('expert_wizard_step2')

    # 1. Guard check for missing session data
    if not step1 or not step2:
        messages.error(request, "Session expired or incomplete registration step.")
        return redirect('expert_register_step1')

    # 2. Build context safely with database lookups
    try:
        context = {
            'step1': step1,
            'category': Category.objects.filter(id=step2.get('category_id')).first(),
            'subcategory': SubCategory.objects.filter(id=step2.get('subcategory_id')).first(),
            'qualification': step2.get('qualification', ''),
            'experience_years': step2.get('experience_years', 0),
            'state': State.objects.filter(id=step2.get('state_id')).first(),
            'district': District.objects.filter(id=step2.get('district_id')).first(),
            'city': City.objects.filter(id=step2.get('city_id')).first(),
            'hourly_rate': step2.get('hourly_rate', 0),
            'bio': step2.get('bio', ''),
        }
    except Exception as e:
        messages.error(request, f"Configuration lookup error: {str(e)}. Restarting setup.")
        return redirect('expert_register_step1')

    # 3. Process Final Registration Submission
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Step A: Create Custom User
                user = User.objects.create_user(
                    username=step1['email'],
                    email=step1['email'],
                    password=step1['password'],
                    first_name=step1['first_name'],
                    last_name=step1['last_name'],
                    phone_number=step1.get('phone_number', ''),
                    role=UserRole.EXPERT
                )

                # Step B: Create Expert Profile
                ExpertProfile.objects.create(
                    user=user,
                    category_id=step2.get('category_id'),
                    subcategory_id=step2.get('subcategory_id'),
                    qualification=step2.get('qualification'),
                    experience_years=step2.get('experience_years', 0),
                    state_id=step2.get('state_id'),
                    district_id=step2.get('district_id'),
                    city_id=step2.get('city_id'),
                    hourly_rate=step2.get('hourly_rate', 0),
                    bio=step2.get('bio', '')
                )

                # Step C: Clean up session keys
                request.session.pop('expert_wizard_step1', None)
                request.session.pop('expert_wizard_step2', None)
                request.session.modified = True

                # Step D: Log in user and redirect to dashboard
                login(request, user)
                messages.success(request, "Expert registration complete! Welcome to Adwise.")
                return redirect('expert_dashboard')

        except Exception as e:
            messages.error(request, f"Registration failed due to a database error: {str(e)}")
            return redirect('expert_register_step3')

    return render(request, 'accounts/expert_step3.html', context)


# ==========================================
# AUTHENTICATION & LOGIN VIEWS
# ==========================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Authenticate via username OR email
            user = authenticate(request, username=username_or_email, password=password)
            if not user:
                try:
                    user_obj = CustomUser.objects.get(email__iexact=username_or_email)
                    user = authenticate(request, username=user_obj.username, password=password)
                except CustomUser.DoesNotExist:
                    pass

            if user is not None:
                login(request, user)
                messages.info(request, f"Welcome back, {user.first_name}!")
                return redirect_by_role(user)
            else:
                messages.error(request, "Invalid username/email or password.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('login')


# ==========================================
# DASHBOARD PLACEHOLDERS (Phase 3 will populate)
# ==========================================
@login_required
def user_dashboard_view(request):
    if request.user.role != UserRole.USER:
        return redirect('expert_dashboard')
    return render(request, 'dashboard/user_dashboard.html')


@login_required
def expert_dashboard_view(request):
    if request.user.role != UserRole.EXPERT:
        return redirect('user_dashboard')
    return render(request, 'dashboard/expert_dashboard.html')




@login_required
def edit_expert_profile_view(request):
    """ Allows experts to update their consultation fee, qualification, and bio """
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Only experts can access profile settings.")
        return redirect('user_dashboard')

    expert_profile = get_object_or_404(ExpertProfile, user=request.user)

    if request.method == 'POST':
        form = ExpertProfileUpdateForm(request.POST, instance=expert_profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Your consultation fee has been updated to ₹{expert_profile.hourly_rate}/hr!")
            return redirect('schedule_manager')
    else:
        form = ExpertProfileUpdateForm(instance=expert_profile)

    return render(request, 'accounts/edit_expert_profile.html', {
        'form': form,
        'expert': expert_profile
    })