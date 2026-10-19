from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/add-language/', views.add_language_view, name='add_language'),
    path('profile/edit-language/<int:language_id>/', views.edit_language_view, name='edit_language'),
    path('profile/delete-language/<int:language_id>/', views.delete_language_view, name='delete_language'),
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    path('block/<int:user_id>/', views.block_user_view, name='block_user'),
    path('report/<int:user_id>/', views.report_user_view, name='report_user'),
]
