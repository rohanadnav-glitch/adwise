from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Schedule Management & Calendar API
    path('schedule/', views.schedule_manager_view, name='schedule_manager'),
    path('schedule/delete/<int:slot_id>/', views.delete_slot_view, name='delete_slot'),
    path('api/calendar-events/', views.get_expert_calendar_events_api, name='get_expert_calendar_events_api'),
    
    # Search Engine & Detail
    path('search/', views.search_experts_view, name='search_experts'),
    path('expert/<int:expert_id>/', views.expert_detail_view, name='expert_detail'),

    # Phase 4: Booking Flow
    path('request/<int:slot_id>/', views.request_session_view, name='request_session'),
    path('expert/requests/', views.expert_requests_view, name='expert_requests'),
    path('expert/action/<int:booking_id>/<str:action>/', views.expert_action_view, name='expert_action'),
    
    # User Bookings & Payment
    path('my-bookings/', views.user_bookings_view, name='user_bookings'),
    path('payment/<int:booking_id>/', views.process_payment_view, name='process_payment'),
    path('postpone-respond/<int:booking_id>/<str:response_action>/', views.respond_postpone_view, name='respond_postpone'),
    
    # Notifications
    path('notifications/', views.notifications_view, name='notifications'),

    path('review/submit/<int:booking_id>/', views.submit_review_view, name='submit_review'),
    path('api/subcategories/', views.get_subcategories_api, name='get_subcategories_api'),
]