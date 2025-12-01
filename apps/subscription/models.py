from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import secrets

class SubscriptionPlan(models.Model):
    """Subscription plan model for different tiers"""
    TIER_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=50)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    billing_cycle = models.CharField(max_length=20, choices=[
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], default='monthly')
    
    # Feature limits
    max_signals_per_day = models.IntegerField(default=5)
    max_portfolios = models.IntegerField(default=1)
    has_ml_predictions = models.BooleanField(default=False)
    has_api_access = models.BooleanField(default=False)
    has_priority_support = models.BooleanField(default=False)
    
    # Trial settings
    trial_days = models.IntegerField(default=7)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
    
    def __str__(self):
        return f"{self.name} - ${self.price}/{self.billing_cycle}"

class UserProfile(models.Model):
    """Extended user profile with subscription information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Subscription info
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    subscription_status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('cancelled', 'Cancelled'),
        ('trial', 'Trial'),
    ], default='inactive')
    
    # Dates
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    
    # Social auth info
    social_provider = models.CharField(max_length=20, null=True, blank=True)
    social_id = models.CharField(max_length=100, null=True, blank=True)
    profile_picture = models.URLField(null=True, blank=True)
    
    # User preferences
    email_verified = models.BooleanField(default=False)
    notification_preferences = models.JSONField(default=dict)
    
    # Usage tracking
    signals_used_today = models.IntegerField(default=0)
    last_signal_reset = models.DateField(auto_now_add=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.email} - {self.subscription_status}"
    
    @property
    def is_subscription_active(self):
        """Check if subscription is currently active"""
        if self.subscription_status == 'trial':
            return self.trial_end_date and self.trial_end_date > timezone.now()
        elif self.subscription_status == 'active':
            return self.subscription_end_date and self.subscription_end_date > timezone.now()
        return False
    
    @property
    def can_use_signals(self):
        """Check if user can use signals based on their plan"""
        if not self.is_subscription_active:
            return False
        
        if self.subscription_plan:
            return self.signals_used_today < self.subscription_plan.max_signals_per_day
        return False
    
    def reset_daily_usage(self):
        """Reset daily usage counters"""
        today = timezone.now().date()
        if self.last_signal_reset < today:
            self.signals_used_today = 0
            self.last_signal_reset = today
            self.save()
    
    def use_signal(self):
        """Mark that a signal was used"""
        self.reset_daily_usage()
        if self.can_use_signals:
            self.signals_used_today += 1
            self.save()
            return True
        return False

class Payment(models.Model):
    """Payment tracking model"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment provider info
    provider = models.CharField(max_length=20, choices=[
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ])
    provider_payment_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - ${self.amount} - {self.status}"

class SubscriptionHistory(models.Model):
    """Track subscription changes"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    old_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='old_subscriptions')
    new_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='new_subscriptions')
    action = models.CharField(max_length=20, choices=[
        ('created', 'Created'),
        ('upgraded', 'Upgraded'),
        ('downgraded', 'Downgraded'),
        ('cancelled', 'Cancelled'),
        ('renewed', 'Renewed'),
    ])
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Subscription History'
        verbose_name_plural = 'Subscription Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.created_at.date()}"


class EmailVerificationToken(models.Model):
    """Model to store email verification tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', 'is_used']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.email} - {self.created_at.date()}"
    
    def is_valid(self):
        """Check if token is still valid"""
        return not self.is_used and timezone.now() < self.expires_at
    
    @classmethod
    def generate_token(cls):
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    def mark_as_used(self):
        """Mark token as used"""
        self.is_used = True
        self.save(update_fields=['is_used'])
