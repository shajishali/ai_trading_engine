from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.backends import ModelBackend
from allauth.socialaccount.models import SocialAccount
from .models import SubscriptionPlan, UserProfile, Payment, SubscriptionHistory
from .forms import CustomSignupForm
from .services import EmailVerificationService
from .decorators import rate_limit_email_action
import json

def signup_view(request):
    """Landing page with social login options and traditional signup"""
    if request.user.is_authenticated:
        return redirect('subscription:subscription_choice')
    
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Inactive until email verified
            user.save()
            
            # Generate and send verification email
            verification_service = EmailVerificationService()
            email_sent = verification_service.send_verification_email(user)
            
            if email_sent:
                messages.success(
                    request,
                    'Account created successfully! Please check your email to verify your account. '
                    'You will be able to access your account once you verify your email address.'
                )
                return redirect('subscription:verification_pending')
            else:
                messages.error(
                    request,
                    'Account created but we could not send the verification email. '
                    'Please contact support or try again later.'
                )
                return redirect('subscription:signup')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomSignupForm()
    
    return render(request, 'subscription/signup.html', {'form': form})

@login_required
def subscription_choice(request):
    """Show subscription options after login/signup"""
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get available plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    context = {
        'plans': plans,
        'user_profile': profile,
    }
    return render(request, 'subscription/subscription_choice.html', context)

@login_required
def start_trial(request):
    """Start free trial for user"""
    if request.method == 'POST':
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Check if user already had a trial
        if profile.subscription_status != 'inactive':
            messages.error(request, 'You have already used your trial period.')
            return redirect('subscription:subscription_choice')
        
        # Get free plan
        free_plan = get_object_or_404(SubscriptionPlan, tier='free')
        
        # Set up trial
        profile.subscription_plan = free_plan
        profile.subscription_status = 'trial'
        profile.subscription_start_date = timezone.now()
        profile.trial_end_date = timezone.now() + timezone.timedelta(days=free_plan.trial_days)
        profile.save()
        
        # Record subscription history
        SubscriptionHistory.objects.create(
            user=request.user,
            new_plan=free_plan,
            action='created'
        )
        
        messages.success(request, f'Free trial started! You have {free_plan.trial_days} days to explore all features.')
        return redirect('dashboard:home')
    
    return redirect('subscription:subscription_choice')

@login_required
def upgrade_subscription(request, plan_id):
    """Upgrade user subscription"""
    if request.method == 'POST':
        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        old_plan = profile.subscription_plan
        
        # Update subscription
        profile.subscription_plan = plan
        profile.subscription_status = 'active'
        profile.subscription_start_date = timezone.now()
        
        # Set end date based on billing cycle
        if plan.billing_cycle == 'monthly':
            profile.subscription_end_date = timezone.now() + timezone.timedelta(days=30)
        else:  # yearly
            profile.subscription_end_date = timezone.now() + timezone.timedelta(days=365)
        
        profile.save()
        
        # Record subscription history
        SubscriptionHistory.objects.create(
            user=request.user,
            old_plan=old_plan,
            new_plan=plan,
            action='upgraded' if old_plan else 'created'
        )
        
        messages.success(request, f'Successfully upgraded to {plan.name}!')
        return redirect('dashboard:home')
    
    return redirect('subscription:subscription_choice')

@login_required
def subscription_management(request):
    """User subscription management page"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    # Get subscription history
    history = SubscriptionHistory.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    # Get payment history
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    context = {
        'user_profile': profile,
        'plans': plans,
        'history': history,
        'payments': payments,
    }
    return render(request, 'subscription/management.html', context)

@login_required
def cancel_subscription(request):
    """Cancel user subscription"""
    if request.method == 'POST':
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        if profile.subscription_status in ['active', 'trial']:
            old_plan = profile.subscription_plan
            profile.subscription_status = 'cancelled'
            profile.save()
            
            # Record subscription history
            SubscriptionHistory.objects.create(
                user=request.user,
                old_plan=old_plan,
                action='cancelled'
            )
            
            messages.success(request, 'Your subscription has been cancelled.')
        else:
            messages.error(request, 'No active subscription to cancel.')
    
    return redirect('subscription:subscription_management')

@csrf_exempt
def webhook_stripe(request):
    """Handle Stripe webhooks for payment processing"""
    if request.method == 'POST':
        try:
            # This is a simplified webhook handler
            # In production, you would verify the webhook signature
            data = json.loads(request.body)
            
            # Handle different webhook events
            event_type = data.get('type')
            
            if event_type == 'payment_intent.succeeded':
                # Handle successful payment
                payment_intent = data['data']['object']
                user_id = payment_intent['metadata'].get('user_id')
                plan_id = payment_intent['metadata'].get('plan_id')
                
                if user_id and plan_id:
                    user = User.objects.get(id=user_id)
                    plan = SubscriptionPlan.objects.get(id=plan_id)
                    
                    # Create payment record
                    Payment.objects.create(
                        user=user,
                        subscription_plan=plan,
                        amount=payment_intent['amount'] / 100,  # Convert from cents
                        currency=payment_intent['currency'].upper(),
                        status='completed',
                        provider='stripe',
                        provider_payment_id=payment_intent['id'],
                        metadata=data
                    )
                    
                    # Update user subscription
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    profile.subscription_plan = plan
                    profile.subscription_status = 'active'
                    profile.subscription_start_date = timezone.now()
                    
                    if plan.billing_cycle == 'monthly':
                        profile.subscription_end_date = timezone.now() + timezone.timedelta(days=30)
                    else:
                        profile.subscription_end_date = timezone.now() + timezone.timedelta(days=365)
                    
                    profile.save()
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

def social_signup_callback(request):
    """Handle post-social-login flow"""
    if request.user.is_authenticated:
        # Check if user has profile
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Update social auth info if available
        social_accounts = SocialAccount.objects.filter(user=request.user)
        if social_accounts.exists():
            social_account = social_accounts.first()
            profile.social_provider = social_account.provider
            profile.social_id = social_account.uid
            
            # Get profile picture if available
            if hasattr(social_account, 'extra_data') and 'picture' in social_account.extra_data:
                profile.profile_picture = social_account.extra_data['picture']
            
            profile.save()
        
        # If user doesn't have an active subscription, redirect to subscription choice
        if not profile.is_subscription_active:
            return redirect('subscription:subscription_choice')
        
        return redirect('dashboard:home')
    
    return redirect('subscription:signup')


def verify_email(request, token):
    """Verify email address using token"""
    verification_service = EmailVerificationService()
    result = verification_service.verify_email_token(token)
    
    if result['success']:
        # Log the user in automatically
        login(request, result['user'], backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, result['message'])
        return redirect('subscription:verification_success')
    else:
        messages.error(request, result['message'])
        return redirect('subscription:verification_error')


def verification_pending(request):
    """Show verification pending page"""
    return render(request, 'subscription/verification_pending.html')


def verification_success(request):
    """Show verification success page"""
    if not request.user.is_authenticated:
        return redirect('subscription:signup')
    
    # Redirect to subscription choice after a short delay
    return render(request, 'subscription/verification_success.html')


def verification_error(request):
    """Show verification error page"""
    return render(request, 'subscription/verification_error.html')


@rate_limit_email_action(action='resend_email', max_attempts=3, cooldown_minutes=5)
def resend_verification(request):
    """Resend verification email with rate limiting"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, 'Please provide your email address.')
            return redirect('subscription:verification_pending')
        
        try:
            user = User.objects.get(email=email)
            verification_service = EmailVerificationService()
            result = verification_service.resend_verification_email(user)
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
        except Exception as e:
            messages.error(request, 'An error occurred. Please try again later.')
        
        return redirect('subscription:verification_pending')
    
    return redirect('subscription:signup')
