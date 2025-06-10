from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    # Template-based views
    path('', views.find_matches, name='find_matches'),
    path('requests/', views.match_requests, name='requests'),
    path('match/<int:match_id>/', views.match_detail, name='match_detail'),
    
    # API endpoints - Match requests
    path('api/send-request/<int:potential_match_id>/', views.send_match_request_api, name='send_request_api'),
    path('api/respond-request/<int:request_id>/', views.respond_to_request_api, name='respond_request_api'),
    path('api/cancel-request/<int:request_id>/', views.cancel_match_request, name='cancel_request'),
    path('api/pending-requests/', views.get_pending_requests, name='get_pending_requests'),
    path('api/request-status/<int:request_id>/', views.check_request_status, name='check_request_status'),
    
    # API endpoints - Match management
    path('api/my-matches/', views.get_my_matches, name='get_my_matches'),
    path('api/match-detail/<int:match_id>/', views.get_match_detail, name='get_match_detail'),
    path('api/end-match/<int:match_id>/', views.end_match, name='end_match'),
    
    # API endpoints - Potential matches
    path('api/potential-matches/', views.get_potential_matches, name='get_potential_matches'),
    path('api/refresh-matches/', views.refresh_potential_matches, name='refresh_matches'),
    
    # API endpoints - Match statistics
    path('api/match-statistics/<int:match_id>/', views.get_match_statistics, name='get_match_statistics'),
    
    # Legacy template views (keeping for backward compatibility)
    path('send-request/<int:potential_match_id>/', views.send_match_request, name='send_request'),
    path('respond/<int:request_id>/', views.respond_to_request, name='respond_request'),
    path('my-matches/', views.my_matches, name='my_matches'),
] 