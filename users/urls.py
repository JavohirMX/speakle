from django.urls import path
from . import views

app_name = 'users'

from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

urlpatterns = [
    path('check-username/', views.check_username_view, name='check_username'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='users/password_reset_form.html', email_template_name='users/password_reset_email.txt', subject_template_name='users/password_reset_subject.txt', success_url=reverse_lazy('users:password_reset_done')), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html', success_url=reverse_lazy('users:password_reset_complete')), name='password_reset_confirm'),
    path('password-reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'), name='password_reset_complete'),
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
