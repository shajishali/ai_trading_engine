from django.urls import path
from . import views

app_name = 'subscription'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('verification-pending/', views.verification_pending, name='verification_pending'),
    path('verification-success/', views.verification_success, name='verification_success'),
    path('verification-error/', views.verification_error, name='verification_error'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('choice/', views.subscription_choice, name='subscription_choice'),
    path('trial/', views.start_trial, name='start_trial'),
    path('upgrade/<int:plan_id>/', views.upgrade_subscription, name='upgrade_subscription'),
    path('management/', views.subscription_management, name='subscription_management'),
    path('cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('webhook/stripe/', views.webhook_stripe, name='webhook_stripe'),
    path('social-callback/', views.social_signup_callback, name='social_signup_callback'),
]

