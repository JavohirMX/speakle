from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('', views.find_matches, name='find_matches'),
    path('send-request/<int:potential_match_id>/', views.send_match_request, name='send_request'),
    path('requests/', views.match_requests, name='requests'),
    path('respond/<int:request_id>/', views.respond_to_request, name='respond_request'),
    path('my-matches/', views.my_matches, name='my_matches'),
    path('match/<int:match_id>/', views.match_detail, name='match_detail'),
] 