from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, ExpertStep1Form, ExpertStep2Form, LoginForm
from .models import CustomUser, UserRole, ExpertProfile
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from apps.categories.models import Category, SubCategory
from apps.locations.models import State, District, City
from django.contrib.auth import get_user_model, login, logout, authenticate
from .models import ExpertCertificate
import os
from .forms import (
    UserRegistrationForm,
    ExpertStep1Form,
    ExpertStep2Form,
    ExpertProfileUpdateForm,
    LoginForm,
)
# ===================================================
# HELPER: ROLE-BASED ACCESS CONTROL REDIRECT
# ===================================================
def redirect_by_role(user):
    # Check string or choice enum match
    if getattr(user, 'role', None) == UserRole.EXPERT or getattr(user, 'role', None) == 'EXPERT':
        return redirect('accounts:expert_dashboard')  # Or 'accounts:expert_dashboard'
    return redirect('accounts:user_dashboard')          # Or 'accounts:user_dashboard'


def home(request):
    # If the user is already logged in, redirect them to their respective dashboard
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    # If guest/anonymous user, render the landing page from templates/home.html
    return render(request, 'home.html')



User = get_user_model()

# ==========================================
# USER REGISTRATION VIEW
# ==========================================
def register_user_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:user_dashboard')

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
            return redirect('accounts:login')
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
            return redirect('accounts:expert_register_step2')
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
        return redirect('accounts:expert_register_step1')

    if request.method == 'POST':
        form = ExpertStep2Form(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            
            # Helper function to get primary key safely whether it's a Model instance or PK integer
            def get_id(obj):
                if hasattr(obj, 'id'):
                    return obj.id
                return obj if obj else None

            # 1. Safely extract the QuerySet into a list of IDs for JSON serialization
            subcategories_qs = cleaned.get('subcategory')
            subcategory_ids_list = list(subcategories_qs.values_list('id', flat=True)) if subcategories_qs else []

            # Store step 2 data safely
            request.session['expert_wizard_step2'] = {
                'category_id': get_id(cleaned.get('category')),
                'subcategory_id': subcategory_ids_list,  # <--- FIXED: Now stores a list of IDs safely
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
            return redirect('accounts:expert_register_step3')
        else:
            messages.error(request, "Please correct the errors in Step 2 below.")
    else:
        # Map stored session _id keys back to actual form fields so the "Back" button works perfectly
        session_data = request.session.get('expert_wizard_step2', {})
        initial_data = {
            'category': session_data.get('category_id'),
            'subcategory': session_data.get('subcategory_id', []),
            'state': session_data.get('state_id'),
            'district': session_data.get('district_id'),
            'city': session_data.get('city_id'),
            'qualification': session_data.get('qualification', ''),
            'experience_years': session_data.get('experience_years', ''),
            'hourly_rate': session_data.get('hourly_rate', ''),
            'bio': session_data.get('bio', ''),
        }
        form = ExpertStep2Form(initial=initial_data)

    return render(request, 'accounts/expert_step2.html', {'form': form})

User = get_user_model()


# ==========================================
# EXPERT REGISTRATION - STEP 3 VIEW
# ==========================================
def expert_register_step3(request):
    step1 = request.session.get('expert_wizard_step1')
    step2 = request.session.get('expert_wizard_step2')

    # 1. Guard check for missing session data
    if not step1 or not step2:
        messages.error(request, "Session expired or incomplete registration step.")
        return redirect('accounts:expert_register_step1')

    # 2. Build context safely with database lookups
    try:
        subcategory_ids = step2.get('subcategory_id', [])
        context = {
            'step1': step1,
            'category': Category.objects.filter(id=step2.get('category_id')).first(),
            'subcategories': SubCategory.objects.filter(id__in=subcategory_ids), # <--- FIXED: Fetches multiple
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
        return redirect('accounts:expert_register_step1')

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
                expert_profile = ExpertProfile.objects.create(
                    user=user,
                    category_id=step2.get('category_id'),
                    # subcategory_id omitted here because ManyToMany fields must be set after creation
                    qualification=step2.get('qualification'),
                    experience_years=step2.get('experience_years', 0),
                    state_id=step2.get('state_id'),
                    district_id=step2.get('district_id'),
                    city_id=step2.get('city_id'),
                    hourly_rate=step2.get('hourly_rate', 0),
                    bio=step2.get('bio', '')
                )

                # Step B.2: Safely attach the multiple subcategories
                if subcategory_ids:
                    expert_profile.subcategories.set(subcategory_ids)

                # Step C: Clean up session keys
                request.session.pop('expert_wizard_step1', None)
                request.session.pop('expert_wizard_step2', None)
                request.session.modified = True

                # Step D: Log in user and redirect to dashboard
                login(request, user)
                messages.success(request, "Expert registration complete! Welcome to Adwise.")
                return redirect('accounts:expert_dashboard')

        except Exception as e:
            messages.error(request, f"Registration failed due to a database error: {str(e)}")
            return redirect('accounts:expert_register_step3')

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
    return redirect('accounts:login')


# ==========================================
# DASHBOARD PLACEHOLDERS 
# ==========================================
@login_required
def user_dashboard_view(request):
    if request.user.role != UserRole.USER:
        return redirect('accounts:expert_dashboard')
    return render(request, 'dashboard/user_dashboard.html')


@login_required
def expert_dashboard_view(request):
    if request.user.role != UserRole.EXPERT:
        return redirect('accounts:user_dashboard')
    return render(request, 'dashboard/expert_dashboard.html')



@login_required
def edit_expert_profile_view(request):
    """ Allows experts to update their profile, photo, documents, social links, and fee """
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Only experts can access profile settings.")
        return redirect('accounts:user_dashboard')

    expert_profile = get_object_or_404(ExpertProfile, user=request.user)

    if request.method == 'POST':
        # NOTE: request.FILES is mandatory to process profile_picture, resume, and certificate
        form = ExpertProfileUpdateForm(request.POST, request.FILES, instance=expert_profile)
        if form.is_valid():
            expert_profile = form.save(commit=False)
            
            # Save base user fields handled in the form
            request.user.first_name = form.cleaned_data.get('first_name')
            request.user.last_name = form.cleaned_data.get('last_name')
            request.user.date_of_birth = form.cleaned_data.get('date_of_birth')
            request.user.save()
            
            expert_profile.save()
            
            messages.success(request, "Your expert profile and settings have been updated successfully!")
            return redirect('accounts:expert_dashboard')
        else:
            messages.error(request, "Please fix the validation errors below.")
    else:
        form = ExpertProfileUpdateForm(instance=expert_profile)

    return render(request, 'accounts/edit_expert_profile.html', {
        'form': form,
        'expert': expert_profile,
        'expert_profile': expert_profile
    })



@login_required
@transaction.atomic
def toggle_expert_availability_view(request):
    """
    Safely toggles an expert's availability status between Available and Unavailable,
    enforcing platform precautions and terms.
    """
    if request.user.role != UserRole.EXPERT:
        messages.error(request, "Access restricted to Expert accounts.")
        return redirect('accounts:user_dashboard')

    expert_profile = get_object_or_404(ExpertProfile, user=request.user)

    if request.method == 'POST':
        agreed_to_terms = request.POST.get('agree_terms') == 'on'
        
        # If going online, terms agreement is mandatory
        if not expert_profile.is_available and not agreed_to_terms:
            messages.error(request, "You must agree to the availability terms and conditions to go online.")
            # FIXED: Used .get() for the META dictionary
            return redirect(request.META.get('HTTP_REFERER') or 'accounts:expert_dashboard')

        # PRECAUTION: Prevent going offline if there are unhandled client booking requests
        if expert_profile.is_available:
            from apps.bookings.models import SessionBooking, SessionStatus
            pending_requests = SessionBooking.objects.filter(
                expert=expert_profile,
                status=SessionStatus.REQUESTED
            ).exists()

            if pending_requests:
                messages.warning(
                    request, 
                    "Precaution Notice: You cannot go offline while you have pending client session requests. Please accept or decline them first."
                )
                # FIXED: Used .get() for the META dictionary
                return redirect(request.META.get('HTTP_REFERER') or 'accounts:expert_dashboard')

        # Execute Toggle
        expert_profile.is_available = not expert_profile.is_available
        expert_profile.availability_toggled_at = timezone.now()
        expert_profile.save(update_fields=['is_available', 'availability_toggled_at'])

        if expert_profile.is_available:
            messages.success(request, "You are now ONLINE and ready for consultation bookings!")
        else:
            messages.info(request, "You are now set to OFFLINE. New clients cannot book instant slots.")

    # FIXED: Used .get() for the META dictionary
    return redirect(request.META.get('HTTP_REFERER') or 'accounts:expert_dashboard')

@login_required
def edit_expert_profile(request):
    """
    Handles viewing and updating expert profile details, 
    dynamic multiple certificates upload, and field validation.
    """
    expert_profile = getattr(request.user, 'expert_profile', None)
    if not expert_profile:
        messages.error(request, "Expert profile not found.")
        return redirect('accounts:home')

    if request.method == 'POST':
        # Track old file paths to clean up if overwritten
        old_pic = expert_profile.profile_picture.path if expert_profile.profile_picture else None
        old_resume = expert_profile.resume.path if expert_profile.resume else None

        form = ExpertProfileUpdateForm(request.POST, request.FILES, instance=expert_profile)
        if form.is_valid():
            with transaction.atomic():
                form.save()

                # Clean up previous local file if a new one was uploaded
                if 'profile_picture' in request.FILES and old_pic and os.path.isfile(old_pic):
                    try:
                        os.remove(old_pic)
                    except OSError:
                        pass

                if 'resume' in request.FILES and old_resume and os.path.isfile(old_resume):
                    try:
                        os.remove(old_resume)
                    except OSError:
                        pass

                # Process dynamically uploaded multiple certificates
                certificate_files = request.FILES.getlist('certificates')
                for cert_file in certificate_files:
                    if cert_file:
                        ExpertCertificate.objects.create(
                            expert=expert_profile, 
                            file=cert_file
                        )

            messages.success(request, "Profile and credentials updated successfully!")
            return redirect('accounts:edit_expert_profile')
        else:
            messages.error(request, "Please correct the highlighted errors below.")
    else:
        form = ExpertProfileUpdateForm(instance=expert_profile)

    return render(request, 'accounts/edit_expert_profile.html', {
        'form': form,
        'expert_profile': expert_profile,
    })


@login_required
def delete_certificate(request, cert_id):
    """
    Deletes an individual certificate from the database and removes the file from disk.
    """
    expert_profile = getattr(request.user, 'expert_profile', None)
    if not expert_profile:
        messages.error(request, "Unauthorized access.")
        return redirect('accounts:home')

    cert = get_object_or_404(ExpertCertificate, id=cert_id, expert=expert_profile)
    
    # Delete the physical file from media storage
    if cert.file and os.path.isfile(cert.file.path):
        try:
            os.remove(cert.file.path)
        except OSError:
            pass

    cert.delete()
    messages.success(request, "Certificate removed successfully.")
    return redirect('accounts:edit_expert_profile')


@login_required
def delete_resume(request):
    """
    Removes the uploaded resume from the expert profile and deletes the file from disk.
    """
    expert_profile = getattr(request.user, 'expert_profile', None)
    if not expert_profile:
        messages.error(request, "Unauthorized access.")
        return redirect('accounts:home')

    if expert_profile.resume:
        # Delete physical file from storage
        if os.path.isfile(expert_profile.resume.path):
            try:
                os.remove(expert_profile.resume.path)
            except OSError:
                pass

        expert_profile.resume = None
        expert_profile.save(update_fields=['resume'])
        messages.success(request, "Resume removed successfully.")
    else:
        messages.info(request, "No resume attached to remove.")

    return redirect('accounts:edit_expert_profile')