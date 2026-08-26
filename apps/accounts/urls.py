from django.urls import path
from . import views
app_name = 'accounts'
urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Registration
    path('register/', views.register_user_view, name='register_user'),
    path('register/default/', views.register_user_view, name='register'),
    path('register/user/', views.register_user_view, name='register_user'),
    path('register/expert/step1/', views.expert_register_step1, name='expert_register_step1'),
    path('register/expert/step2/', views.expert_register_step2, name='expert_register_step2'),
    path('register/expert/step3/', views.expert_register_step3, name='expert_register_step3'),
    
    # Role-based Dashboards
    path('dashboard/user/', views.user_dashboard_view, name='user_dashboard'),
    path('dashboard/expert/', views.expert_dashboard_view, name='expert_dashboard'),
    path('expert/profile/edit/', views.edit_expert_profile_view, name='edit_expert_profile'),
    path('expert/edit-profile/', views.edit_expert_profile_view, name='edit_expert_profile'),
    path('expert/toggle-availability/', views.toggle_expert_availability_view, name='toggle_availability'),
    path('expert/certificate/delete/<int:cert_id>/', views.delete_certificate, name='delete_certificate'),
    path('expert/resume/delete/', views.delete_resume, name='delete_resume'),
    
]